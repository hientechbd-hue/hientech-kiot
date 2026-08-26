import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# --- CHUỖI KẾT NỐI SUPABASE POOLER CHUẨN XÁC 100% ---
DATABASE_URL = "postgresql://postgres.xjjushvfwvkozyfucmqc:thanhhientran097@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"

# Khởi tạo engine kết nối an toàn cho Render
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==================== DỊCH VỤ DATABASE TABLES ====================

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

class ServiceTicketDB(Base):
    __tablename__ = "service_tickets"
    id = Column(Integer, primary_key=True, index=True)
    ticket_code = Column(String, unique=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    serial_number = Column(String, nullable=False)
    issue_description = Column(String, nullable=False)
    status = Column(String, default="RECEIVED")  # RECEIVED -> REPAIRING -> COMPLETED -> RETURNED
    notes = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

# ==================== FASTAPI APP CONFIG (Đã đổi version v2 để ép Render nhận diện mới) ====================

app = FastAPI(title="Kiot May Tinh API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi động an toàn: Tránh làm sập app Render nếu kết nối DB bị độ trễ lúc bật
@app.on_event("startup")
def startup_event():
    try:
        Base.metadata.create_all(bind=engine)
        print("--- Kết nối cơ sở dữ liệu Supabase thành công! ---")
    except Exception as e:
        print(f"--- Cảnh báo khởi tạo Database lúc bật app: {e} ---")

# ==================== REQUEST MODELS ====================

class SellRequest(BaseModel):
    serial_number: str

class CreateTicketRequest(BaseModel):
    customer_name: str
    customer_phone: str
    serial_number: str
    issue_description: str

class UpdateTicketStatusRequest(BaseModel):
    ticket_code: str
    status: str
    notes: str = ""

# ==================== API ENDPOINTS ====================

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Hệ thống Bán hàng & Bảo hành đang hoạt động v2!"}

# --- 1. API BÁN HÀNG & TRA CỨU SERIAL ---

@app.post("/sell/")
def sell_product(req: SellRequest):
    db = SessionLocal()
    try:
        serial = db.query(SerialDB).filter(SerialDB.serial_number == req.serial_number).first()
        if not serial:
            raise HTTPException(status_code=404, detail="Không tìm thấy Serial này trong kho!")
        if serial.status == "SOLD":
            raise HTTPException(status_code=400, detail="Thiết bị mang Serial này ĐÃ BÁN rồi!")

        serial.status = "SOLD"
        product = db.query(ProductDB).filter(ProductDB.id == serial.product_id).first()
        if product and product.stock > 0:
            product.stock -= 1
        db.commit()
        return {"message": f"Xuất bán thành công Serial: {req.serial_number}"}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
    finally:
        db.close()

@app.get("/search-sn/{sn}")
def search_serial(sn: str):
    db = SessionLocal()
    try:
        serial = db.query(SerialDB).filter(SerialDB.serial_number == sn).first()
        if not serial:
            raise HTTPException(status_code=404, detail="Serial không tồn tại!")
        product = db.query(ProductDB).filter(ProductDB.id == serial.product_id).first()
        return {
            "serial": serial.serial_number,
            "status": serial.status,
            "product_name": product.name if product else "N/A",
            "price": product.price if product else 0
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
    finally:
        db.close()

# --- 2. API QUẢN LÝ BẢO HÀNH & SỬA CHỮA ---

@app.post("/tickets/create/")
def create_ticket(req: CreateTicketRequest):
    db = SessionLocal()
    try:
        ticket_code = f"BH-{int(datetime.now().timestamp())}"
        new_ticket = ServiceTicketDB(
            ticket_code=ticket_code,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
            serial_number=req.serial_number,
            issue_description=req.issue_description,
            status="RECEIVED"
        )
        db.add(new_ticket)
        db.commit()
        return {"message": "Tạo phiếu thành công!", "ticket_code": ticket_code}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi tạo phiếu: {str(e)}")
    finally:
        db.close()

@app.post("/tickets/update-status/")
def update_ticket_status(req: UpdateTicketStatusRequest):
    db = SessionLocal()
    try:
        ticket = db.query(ServiceTicketDB).filter(ServiceTicketDB.ticket_code == req.ticket_code).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Không tìm thấy mã phiếu!")
        
        ticket.status = req.status
        if req.notes:
            ticket.notes = req.notes
        db.commit()
        return {"message": f"Đã cập nhật phiếu {req.ticket_code} sang trạng thái: {req.status}"}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật: {str(e)}")
    finally:
        db.close()

@app.get("/tickets/track/{query}")
def track_ticket(query: str):
    db = SessionLocal()
    try:
        tickets = db.query(ServiceTicketDB).filter(
            (ServiceTicketDB.ticket_code == query) | 
            (ServiceTicketDB.customer_phone == query) |
            (ServiceTicketDB.serial_number == query)
        ).all()
        
        if not tickets:
            raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu bảo hành phù hợp!")
        
        res = []
        for t in tickets:
            res.append({
                "ticket_code": t.ticket_code,
                "customer_name": t.customer_name,
                "customer_phone": t.customer_phone,
                "serial_number": t.serial_number,
                "issue": t.issue_description,
                "status": t.status,
                "notes": t.notes,
                "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "N/A"
            })
        return res
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tra cứu: {str(e)}")
    finally:
        db.close()
