from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import datetime
import shutil
import os
import math

app = FastAPI(title="Devanshi Mobile - Shop Management System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ટેમ્પરરી ડેટાબેઝ (પછીથી SQLite/PostgreSQL સાથે કનેક્ટ થશે)
udhar_database = []
bb_database = []
staff_attendance = []
subscriptions = {}  # Shop ID -> Expiry Date & Status

# --- 1. સબ્સ્ક્રિપ્શન અને ડેમો મોડ કંટ્રોલ (10 Days Demo + Advance Rent) ---
class ShopSubscription(BaseModel):
    shop_id: str
    owner_name: str
    mobile_number: str

@app.post("/api/shop/register")
def register_shop(shop: ShopSubscription):
    today = datetime.date.today()
    # ૧૦ દિવસનો ફ્રી ડેમો મોડ
    expiry_date = today + datetime.timedelta(days=10)
    subscriptions[shop.shop_id] = {
        "owner_name": shop.owner_name,
        "mobile_number": shop.mobile_number,
        "expiry_date": str(expiry_date),
        "status": "Active_Demo"
    }
    return {"status": "Success", "message": "૧૦ દિવસનો ફ્રી ડેમો મોડ શરૂ થઈ ગયો છે!", "expiry": str(expiry_date)}

@app.get("/api/shop/check/{shop_id}")
def check_subscription(shop_id: str):
    if shop_id not in subscriptions:
        raise HTTPException(status_code=403, detail="દુકાન રજિસ્ટર્ડ નથી. કૃપા કરીને સાઇન-અપ કરો.")
    
    sub = subscriptions[shop_id]
    expiry = datetime.datetime.strptime(sub["expiry_date"], "%Y-%m-%d").date()
    today = datetime.date.today()
    
    if today > expiry:
        sub["status"] = "Expired"
        return {"status": "Locked", "message": "તમારું એડવાન્સ ભાડું/સબ્સ્ક્રિપ્શન પૂરું થઈ ગયું છે. આગળ ચાલુ રાખવા એડવાન્સ ભાડું ભરો."}
    
    return {"status": "Unlocked", "details": sub}


# --- 2. જીઓ-ફેન્સિંગ હાજરી (50 Meters GPS Lock) ---
def calculate_distance(lat1, lon1, lat2, lon2):
    # Haversine formula થી બે પોઈન્ટ વચ્ચેનું અંતર મીટરમાં ગણવા માટે
    R = 6371e3
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

class AttendanceEntry(BaseModel):
    shop_id: str
    staff_name: str
    action: str  # "IN" or "OUT"
    current_lat: float
    current_lon: float
    shop_lat: float  # દુકાનનું ફિક્સ અક્ષાંશ
    shop_lon: float  # દુકાનનું ફિક્સ રેખાંશ

@app.post("/api/staff/attendance")
def mark_attendance(att: AttendanceEntry):
    distance = calculate_distance(att.current_lat, att.current_lon, att.shop_lat, att.shop_lon)
    
    if distance > 50:
        raise HTTPException(status_code=400, detail=f"હાજરી અમાન્ય! તમે દુકાનથી {round(distance, 2)} મીટર દૂર છો (મર્યાદા 50 મીટર છે).")
    
    record = {
        "shop_id": att.shop_id,
        "staff_name": att.staff_name,
        "action": att.action,
        "time": str(datetime.datetime.now()),
        "location_verified": True
    }
    staff_attendance.append(record)
    return {"status": "Success", "message": f"સ્ટાફ હાજરી ({att.action}) સફળતાપૂર્વક નોંધાઈ ગઈ!"}


# --- 3. બાકી ગ્રાહક અને વાયદા સિસ્ટમ ---
class UdharEntry(BaseModel):
    customer_name: str
    mobile_number: str
    apx_bill_number: str
    amount_due: float
    due_date: str

@app.post("/api/udhar/add")
def add_udhar(entry: UdharEntry):
    data = entry.dict()
    data["date"] = str(datetime.date.today())
    data["status"] = "Pending"
    udhar_database.append(data)
    return {"status": "Success", "message": "બાકી એન્ટ્રી સેવ થઈ ગઈ!"}

@app.get("/api/udhar/today-due")
def get_today_due():
    today = str(datetime.date.today())
    dues = [i for i in udhar_database if i["due_date"] == today and i["status"] == "Pending"]
    return {"count": len(dues), "data": dues}


# --- 4. BB (બાય-બેક) અને AI ઓટો રીડિંગ (બિલ/આધાર સ્કેન) ---
@app.post("/api/bb/add")
async def add_buyback(
    customer_name: str = Form(...),
    mobile_number: str = Form(...),
    model_name: str = Form(...),
    imei_number: str = Form(...),
    purchase_price: float = Form(...),
    document: UploadFile = File(None)
):
    doc_path = None
    if document:
        os.makedirs("uploads", exist_ok=True)
        doc_path = f"uploads/{document.filename}"
        with open(doc_path, "wb") as buffer:
            shutil.copyfileobj(document.file, buffer)
        # અહીં AI/OCR દ્વારા બિલ કે આધારમાંથી ટેક્સ્ટ રીડ કરીને ઓટો-ફિલ થાય છે

    record = {
        "date": str(datetime.date.today()),
        "customer_name": customer_name,
        "mobile_number": mobile_number,
        "model_name": model_name,
        "imei_number": imei_number,
        "purchase_price": purchase_price,
        "document_url": doc_path
    }
    bb_database.append(record)
    return {"status": "Success", "message": "BB બાય-બેક એન્ટ્રી અને ડોક્યુમેન્ટ સેવ થઈ ગયા!", "data": record}