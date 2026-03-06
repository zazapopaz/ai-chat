# delete_admin.py
import asyncio
from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from app.models.admin import Admin


async def delete_admin_by_email(email: str):
    """Удалить админа по email"""
    print(f"🔍 Поиск администратора с email: {email}")

    async with AsyncSessionLocal() as db:
        # Находим админа
        result = await db.execute(
            select(Admin).where(Admin.email == email)
        )
        admin = result.scalar_one_or_none()

        if not admin:
            print(f"❌ Администратор с email {email} не найден")
            return False

        print(f"✅ Найден администратор:")
        print(f"   ID: {admin.id}")
        print(f"   Email: {admin.email}")
        print(f"   Супер-админ: {'Да' if admin.is_superadmin else 'Нет'}")
        print(f"   Имя: {admin.full_name or 'Не указано'}")

        # Удаляем
        await db.delete(admin)
        await db.commit()

        print(f"✅ Администратор {email} успешно удален")
        return True


async def delete_admin_by_id(admin_id: str):
    """Удалить админа по ID"""
    print(f"🔍 Поиск администратора с ID: {admin_id}")

    async with AsyncSessionLocal() as db:
        # Находим админа
        result = await db.execute(
            select(Admin).where(Admin.id == admin_id)
        )
        admin = result.scalar_one_or_none()

        if not admin:
            print(f"❌ Администратор с ID {admin_id} не найден")
            return False

        print(f"✅ Найден администратор:")
        print(f"   ID: {admin.id}")
        print(f"   Email: {admin.email}")
        print(f"   Супер-админ: {'Да' if admin.is_superadmin else 'Нет'}")

        # Удаляем
        await db.delete(admin)
        await db.commit()

        print(f"✅ Администратор {admin.email} успешно удален")
        return True


async def list_all_admins():
    """Показать всех админов"""
    print("📋 Список всех администраторов:")
    print("-" * 60)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Admin).order_by(Admin.created_at)
        )
        admins = result.scalars().all()

        if not admins:
            print("❌ Администраторы не найдены")
            return []

        for admin in admins:
            print(f"ID: {admin.id}")
            print(f"Email: {admin.email}")
            print(f"Супер-админ: {'✅' if admin.is_superadmin else '❌'}")
            print(f"Имя: {admin.full_name or 'Не указано'}")
            print(f"Создан: {admin.created_at}")
            print(f"Последний вход: {admin.last_login or 'Никогда'}")
            print("-" * 60)

        return admins


async def main():
    print("=" * 60)
    print("🔧 УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ")
    print("=" * 60)

    # Сначала показываем всех админов
    await list_all_admins()

    print("\nВыберите действие:")
    print("1. Удалить админа по email")
    print("2. Удалить админа по ID")
    print("3. Показать всех админов")
    print("4. Выйти")

    choice = input("\nВаш выбор (1-4): ").strip()

    if choice == '1':
        email = input("Введите email админа для удаления: ").strip()
        await delete_admin_by_email(email)
    elif choice == '2':
        admin_id = input("Введите ID админа для удаления: ").strip()
        await delete_admin_by_id(admin_id)
    elif choice == '3':
        await list_all_admins()
    else:
        print("До свидания!")


if __name__ == "__main__":
    asyncio.run(main())