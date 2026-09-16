from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import AsyncSessionLocal, engine, Base, get_db
import model, schemas, checker, auth
from datetime import datetime
import time
import asyncio
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import oauth2, OAuth2PasswordRequestForm
from auth import get_current_user, pwd_context, create_access_token

background_task = None

async def periodic_checker():
    while True:
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(model.Website))
                websites = result.scalars().all()
                if websites:
                    check_result = await checker.concurrent_check_all_sequential([w.url for w in websites])
                    for website, result_data in zip(websites, check_result):
                        db.add(model.Check(
                            website_id=website.id,
                            status_code=result_data["status_code"],
                            response_time_ms=result_data["response_time_ms"],
                            is_up=result_data["is_up"],
                            checked_at=datetime.utcnow(),
                        ))
                    await db.commit()
                    print(f"Checked: {len(websites)}")
        except Exception as e:
            print(f"Background check failed: {e}")

        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    global background_task
    background_task = asyncio.create_task(periodic_checker())
    yield
    background_task.cancel()
    try:
        await background_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/websites", response_model= schemas.WebsiteOut)
async def add_website(website: schemas.WebsiteCreate, db: AsyncSession = Depends(get_db), user: model.User = Depends(get_current_user)):
    result = await db.execute(select(model.Website).where(model.Website.url==str(website.url)))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Url already being monitored")
    
    db_website = model.Website(url=str(website.url), owner_id=user.id)
    db.add(db_website)
    await db.commit()
    await db.refresh(db_website)
    return db_website

@app.get("/websites", response_model=list[schemas.WebsiteOut])
async def list_website(db:AsyncSession = Depends(get_db), user: model.User = Depends(get_current_user)):
    stmt = select(model.Website).where(model.Website.owner_id == user.id)
    latest_check_subq = (
        select(
            model.Check.website_id,
            func.max(model.Check.checked_at).label("max_checked_at")
        )
        .group_by(model.Check.website_id)
        .subquery()
    )

    stmt = (
        select(
            model.Website,
            model.Check.is_up,
            model.Check.status_code,
            model.Check.response_time_ms,
            model.Check.checked_at,
        )
        .outerjoin(latest_check_subq, model.Website.id == latest_check_subq.c.website_id)
        .outerjoin(
            model.Check,
            (model.Check.website_id == latest_check_subq.c.website_id)
            & (model.Check.checked_at == latest_check_subq.c.max_checked_at)
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": w.id,
            "url": w.url,
            "created_at": w.created_at,
            "is_up": is_up,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "last_checked": checked_at,
        }
        for w, is_up, status_code, response_time_ms, checked_at in rows
    ]

@app.delete("/websites",response_model=schemas.WebsiteDelete)
async def delete_website(website: schemas.WebsiteDelete, db:AsyncSession = Depends(get_db)):
    stmt = delete(model.Website).where(model.Website.url==str(website.url))
    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="URL not found.")
    
    await db.commit()
    return {"URL Succesfully deleted": result}

@app.get("/website/check-all")
async def check_all_website(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(model.Website))
    websites = result.scalars().all()

    check_result = await checker.concurrent_check_all_sequential([w.url for w in websites])

    for website, result_data in zip(websites, check_result):
        check = model.Check(
            website_id=website.id,
            status_code=result_data["status_code"],
            response_time_ms=result_data["response_time_ms"],
            is_up=result_data["is_up"],
            checked_at=datetime.utcnow(),
        )
        db.add(check)
    await db.commit()
    return {"checked": len(websites)}


@app.get("/website/{website_id}/history", response_model=list[schemas.CheckOut])
async def get_history(website_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(model.Check)
        .where(model.Check.website_id == website_id)
        .order_by(model.Check.checked_at.desc())
        .limit(50)
    )
    return result.scalars().all()

@app.post("/register")
async def register(email: str, password: str, db: AsyncSession = Depends(get_db)):
    hashed = pwd_context.hash(password)
    user = model.User(email=email, hashed_password=hashed)
    db.add(user)
    await db.commit()
    return {"message": "registered"}

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(model.User).where(model.User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/health")
    async def health():
    return {"ok": True}
