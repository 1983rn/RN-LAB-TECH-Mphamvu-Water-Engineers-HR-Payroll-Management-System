from app import app
from models import Client, db

with app.app_context():
    total = Client.query.count()
    borehole = Client.query.filter_by(department='Borehole Drilling').count()
    construction = Client.query.filter_by(department='Construction').count()
    print(f'Total clients: {total}')
    print(f'Borehole clients: {borehole}')
    print(f'Construction clients: {construction}')
