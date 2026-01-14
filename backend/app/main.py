from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import exercises

app = FastAPI(title="English Tutor AI")

# Разрешаем фронтенду (Angular) стучаться на бекенд
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Адрес Angular по умолчанию
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(exercises.router, prefix="/api/v1/exercises", tags=["exercises"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
