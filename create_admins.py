from app import app, db, Admin

with app.app_context():
    admin1 = Admin(username="admin1")
    admin1.set_password("password123")  # must use set_password
    db.session.add(admin1)
    db.session.commit()
    print("Admin user created successfully!")