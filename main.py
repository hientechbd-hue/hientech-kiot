from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "postgresql://postgres:Xisoho097@@@db.xjjushvfwvkozyfucmqc.supabase.co:5432/postgres"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ProductDB(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)

class SerialDB(Base):
    __tablename__ = "serial_numbers"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    serial_number = Column(String, unique=True, nullable=False)
    status = Column(String, default="AVAILABLE")

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SellRequest(BaseModel):
    serial_number: str

@app.post("/sell/")
def sell_product(req: SellRequest):
    db = SessionLocal()
    serial = db.query(SerialDB).filter(SerialDB.serial_number == req.serial_number).first()
    if not serial:
        db.close()
        raise HTTPException(status_code=404, detail="Không tìm thấy Serial này trong kho!")
    if serial.status == "SOLD":
        db.close()
        raise HTTPException(status_code=400, detail="Thiết bị mang Serial này ĐÃ BÁN rồi!")

    serial.status = "SOLD"
    product = db.query(ProductDB).filter(ProductDB.id == serial.product_id).first()
    if product and product.stock > 0:
        product.stock -= 1
    db.commit()
    db.close()
    return {"message": f"Xuất bán thành công Serial: {req.serial_number}"}

@app.get("/search-sn/{sn}")
def search_serial(sn: str):
    db = SessionLocal()
    serial = db.query(SerialDB).filter(SerialDB.serial_number == sn).first()
    if not serial:
        db.close()
        raise HTTPException(status_code=404, detail="Serial không tồn tại!")
    product = db.query(ProductDB).filter(ProductDB.id == serial.product_id).first()
    db.close()
    return {
        "serial": serial.serial_number,
        "status": serial.status,
        "product_name": product.name if product else "N/A",
        "price": product.price if product else 0
    }