import cv2
import base64
import numpy as np
import os
import uuid

# Load pre-trained cascades from OpenCV
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

def calculate_ear_opencv(eye_region_gray):
    """
    Estimates blink state from an eye ROI using OpenCV contour analysis.
    Returns True if the eye appears open, False if closed/blinking.
    """
    if eye_region_gray is None or eye_region_gray.size == 0:
        return True  # Default to open if can't detect

    # Threshold and find contours
    _, thresh = cv2.threshold(eye_region_gray, 50, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return False  # No visible iris = eye likely closed
    
    # Largest contour = iris/pupil
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    roi_area = eye_region_gray.shape[0] * eye_region_gray.shape[1]
    
    # If iris area is very small relative to eye ROI, eye is likely closed
    ratio = area / roi_area if roi_area > 0 else 0
    return ratio > 0.05  # Open if iris fills >5% of ROI


def verify_face_in_base64_image(base64_str):
    """
    Decodes the base64 image and uses OpenCV to detect if there is AT LEAST ONE face.
    Improved with histogram equalization for better lighting handling.
    Returns (True, saved_path) if a face is detected, (False, None) otherwise.
    """
    try:
        # 1. Clean and decode
        if ',' in base64_str:
            base64_str = base64_str.split(',', 1)[1]
            
        img_data = base64.b64decode(base64_str)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return False, None

        # 2. Pre-process for detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply CLAHE for better adaptive contrast in varied lighting
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        # Multi-pass face detection: try strict first, then progressively relax
        faces = []
        detection_params = [
            (1.1, 5, (60, 60)),   # Strict: close-up faces
            (1.1, 3, (40, 40)),   # Medium: slightly relaxed
            (1.05, 3, (30, 30)),  # Relaxed: smaller faces / further away
        ]
        
        for scale, neighbors, min_size in detection_params:
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=scale,
                minNeighbors=neighbors,
                minSize=min_size
            )
            if len(faces) > 0:
                break
        
        if len(faces) == 0:
            return False, None
            
        # 3. Save as evidence
        os.makedirs("static/attendance_evidence", exist_ok=True)
        filename = f"evidence_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join("static/attendance_evidence", filename)
        
        cv2.imwrite(filepath, img)
        return True, filepath

    except Exception as e:
        print(f"Error in biometric verification: {e}")
        return False, None

def _detect_face_multipass(gray_img):
    """Helper: detect a face using progressively relaxed parameters."""
    detection_params = [
        (1.1, 5, (60, 60)),
        (1.1, 3, (40, 40)),
        (1.05, 3, (30, 30)),
    ]
    for scale, neighbors, min_size in detection_params:
        faces = face_cascade.detectMultiScale(gray_img, scale, neighbors, minSize=min_size)
        if len(faces) > 0:
            return faces[0]  # Return the first detected face
    return None

def _preprocess_face(gray_img):
    """Apply CLAHE for lighting normalization."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray_img)

FACE_MATCH_SIZE = (200, 200)  # Normalize all faces to this size for comparison

def verify_face_match(captured_img_path, employee_photo_path):
    """
    Compares the captured face against the stored employee photo using OpenCV LBPH.
    Uses CLAHE preprocessing and normalized face sizes for reliable comparison.
    """
    try:
        # Create a temporary recognizer for one-to-one match
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        
        # Load and preprocess known (employee) image
        known_img = cv2.imread(employee_photo_path, cv2.IMREAD_GRAYSCALE)
        if known_img is None: return False
        known_img = _preprocess_face(known_img)
        
        # Detect face in known image
        face_rect = _detect_face_multipass(known_img)
        if face_rect is None: return False
        (x, y, w, h) = face_rect
        known_face = cv2.resize(known_img[y:y+h, x:x+w], FACE_MATCH_SIZE)
        
        # Train on this one face
        recognizer.train([known_face], np.array([1]))
        
        # Load and preprocess captured (webcam) image
        unknown_img = cv2.imread(captured_img_path, cv2.IMREAD_GRAYSCALE)
        if unknown_img is None: return False
        unknown_img = _preprocess_face(unknown_img)
        
        # Detect face in captured image
        face_rect = _detect_face_multipass(unknown_img)
        if face_rect is None: return False
        (x, y, w, h) = face_rect
        unknown_face = cv2.resize(unknown_img[y:y+h, x:x+w], FACE_MATCH_SIZE)
        
        # Predict
        label, confidence = recognizer.predict(unknown_face)
        
        # LBPH: lower confidence = better match. 
        # Webcam vs stored photo typically scores 50-100 for same person.
        print(f"LBPH Match confidence: {confidence:.1f} (threshold: 95)")
        return confidence < 95

    except Exception as e:
        print(f"Error matching faces: {e}")
        return False

class MultiFaceRecognizer:
    """
    Handles real-time identification of multiple employees from video frames 
    using OpenCV LBPH (Robust) and OpenCV Eye-Detection Anti-Spoofing.
    """
    def __init__(self):
        self.known_employee_data = {} # {label_id: {'id': employee_id, 'name': 'First Last'}}
        self.last_marked = {} 
        self.blink_status = {} 
        self.cooldown_seconds = 60
        self.blink_consecutive_frames = 2
        
        # OpenCV Recognizer
        try:
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            self.is_trained = False
        except AttributeError:
            print("ERROR: opencv-contrib-python not installed. Face recognition will fail.")
            self.recognizer = None
            self.is_trained = False

    def load_known_faces(self):
        """
        Loads all active employee photos and trains the LBPH recognizer.
        """
        if self.recognizer is None:
            return

        from models import Employee
        active_employees = Employee.query.filter_by(status='Active').all()
        
        faces = []
        labels = []
        self.known_employee_data = {}

        label_id = 0
        for emp in active_employees:
            if emp.photo_path:
                photo_path = emp.photo_path
                if not os.path.isabs(photo_path):
                    photo_path = os.path.join('static', photo_path)
                
                if os.path.exists(photo_path):
                    try:
                        # Load, convert to grayscale, and apply CLAHE
                        img = cv2.imread(photo_path, cv2.IMREAD_GRAYSCALE)
                        if img is None: continue
                        img = _preprocess_face(img)
                        
                        # Detect face using multi-pass
                        face_rect = _detect_face_multipass(img)
                        if face_rect is not None:
                            (x, y, w, h) = face_rect
                            face_crop = cv2.resize(img[y:y+h, x:x+w], FACE_MATCH_SIZE)
                            faces.append(face_crop)
                            labels.append(label_id)
                            
                            self.known_employee_data[label_id] = {
                                'id': emp.employee_id,
                                'emp_no': emp.employment_number,
                                'name': f"{emp.first_name} {emp.last_name}"
                            }
                            label_id += 1
                            break # Only take one face per photo
                    except Exception as e:
                        print(f"Error training on employee {emp.employment_number}: {e}")

        if faces:
            self.recognizer.train(faces, np.array(labels))
            self.is_trained = True
            print(f"LBPH Recognizer trained with {len(faces)} employee faces.")

    def _detect_eyes_in_face(self, gray_face):
        """
        Detects eyes within a face ROI using OpenCV Haar cascade.
        Returns the number of eyes detected and whether they appear open.
        """
        eyes = eye_cascade.detectMultiScale(
            gray_face,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(20, 20)
        )
        
        eyes_open = 0
        for (ex, ey, ew, eh) in eyes:
            eye_roi = gray_face[ey:ey+eh, ex:ex+ew]
            if calculate_ear_opencv(eye_roi):
                eyes_open += 1
        
        return len(eyes), eyes_open

    def process_frame(self, frame):
        """
        Detects faces via Haar Cascade, identifies via LBPH, and detects blinks via OpenCV eye cascade.
        """
        if not self.is_trained:
            return frame, []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = _preprocess_face(gray)  # Apply same CLAHE as training
        
        # Resize for faster face detection
        small_gray = cv2.resize(gray, (0, 0), fx=0.5, fy=0.5)
        detected_faces = face_cascade.detectMultiScale(small_gray, 1.1, 3, minSize=(30, 30))

        verified_employees = []

        for (x, y, w, h) in detected_faces:
            # Scale back up
            x, y, w, h = x*2, y*2, w*2, h*2
            
            face_crop = cv2.resize(gray[y:y+h, x:x+w], FACE_MATCH_SIZE)  # Same size as training
            label_id, confidence = self.recognizer.predict(face_crop)
            
            name = "Unknown"
            emp_id = None
            emp_data = None
            status_prefix = ""

            # LBPH: lower confidence = better match. Threshold 95 for webcam conditions.
            if label_id in self.known_employee_data and confidence < 95:
                emp_data = self.known_employee_data[label_id]
                name = emp_data['name']
                emp_id = emp_data['id']
                
                # Anti-spoofing: Blink detection using OpenCV eye cascade
                num_eyes, eyes_open = self._detect_eyes_in_face(face_crop)
                
                if emp_id not in self.blink_status:
                    self.blink_status[emp_id] = {'count': 0, 'verified': False}
                
                if num_eyes >= 1:
                    # Eyes detected but appear closed (blinking)
                    if eyes_open == 0:
                        self.blink_status[emp_id]['count'] += 1
                    else:
                        # Eyes are open — if we had enough closed frames, it's a blink
                        if self.blink_status[emp_id]['count'] >= self.blink_consecutive_frames:
                            self.blink_status[emp_id]['verified'] = True
                        self.blink_status[emp_id]['count'] = 0
                else:
                    # No eyes detected at all (could be closed or bad angle)
                    self.blink_status[emp_id]['count'] += 1

                # Verification Status
                if emp_id in self.blink_status and self.blink_status[emp_id]['verified']:
                    verified_employees.append(emp_data)
                    status_prefix = "Verified: "
                else:
                    status_prefix = "Blink to Verify: "

            # UI Rendering
            color = (0, 255, 0) if (emp_id and self.blink_status.get(emp_id, {}).get('verified')) else (0, 165, 255)
            if name == "Unknown": color = (0, 0, 255)
            
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            cv2.rectangle(frame, (x, y+h - 35), (x+w, y+h), color, cv2.FILLED)
            display_text = f"{status_prefix}{name}" if name != 'Unknown' else name
            cv2.putText(frame, display_text, (x + 6, y+h - 6), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)

        return frame, verified_employees
