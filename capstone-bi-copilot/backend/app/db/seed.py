from app.db.session import Base,engine,SessionLocal
from app.db.models import User,Sale
from app.core.security import hash_password

def init_database() -> None:
    Base.metadata.create_all(engine)
    db=SessionLocal()
    try:
        if db.query(User).count()==0:
            db.add_all([
                User(email="admin@example.com",password_hash=hash_password("Admin123!"),role="admin"),
                User(email="manager@example.com",password_hash=hash_password("Manager123!"),role="manager"),
            ])
        if db.query(Sale).count()==0:
            rows=[
                ("2026-06-01","North","Enterprise Suite",120000,78000,82),
                ("2026-07-01","North","Enterprise Suite",105000,71000,75),
                ("2026-08-01","North","Enterprise Suite",150000,96000,103),
                ("2026-06-01","South","Analytics Pro",92000,51000,61),
                ("2026-07-01","South","Analytics Pro",98000,54000,66),
                ("2026-08-01","South","Analytics Pro",110000,59000,73),
            ]
            db.add_all([Sale(sale_date=d,region=r,product=p,revenue=rev,cost=c,orders=o) for d,r,p,rev,c,o in rows])
        db.commit()
    finally: db.close()
