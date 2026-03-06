#backend/app/api/__init__.py
from fastapi import APIRouter
from app.api.endpoints import auth, tenants, widget, dashboard, admin

print("=" * 60)
print("🔍 ЗАГРУЗКА API РОУТЕРОВ")
print("=" * 60)

# Проверяем наличие роутеров
print(f"✅ auth роутер: {hasattr(auth, 'router')}")
print(f"✅ tenants роутер: {hasattr(tenants, 'router')}")
print(f"✅ widget роутер: {hasattr(widget, 'router')}")
print(f"✅ dashboard роутер: {hasattr(dashboard, 'router')}")
print(f"✅ admin роутер: {hasattr(admin, 'router')}")

# Создаем главный роутер
api_router = APIRouter()

# Подключаем все роутеры
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(widget.router, prefix="/widget", tags=["widget"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])  # ЭТО КЛЮЧЕВАЯ СТРОКА!

print(f"\n📊 ВСЕГО РОУТОВ В API: {len(api_router.routes)}")

# Выводим все пути для проверки
print("\n📋 СПИСОК ВСЕХ ПУТЕЙ:")
for route in api_router.routes:
    if hasattr(route, "path"):
        print(f"  {route.path}")

print("=" * 60)