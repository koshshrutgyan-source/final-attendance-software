from app import app, db  # replace with actual file names

with app.app_context():
    db.create_all()
    print("Database created successfully!")