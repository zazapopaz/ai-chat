import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from app.models.user import User
from app.crud import crud_user


async def delete_user_by_email(email: str):
    async with AsyncSessionLocal() as db:
        # Найти пользователя
        user = await crud_user.get_by_email(db, email)
        if user:
            print(f"Найден пользователь: {user.email}, ID: {user.id}")

            # Удалить через сессию
            await db.delete(user)
            await db.commit()
            print(f"Пользователь {email} удален")
        else:
            print(f"Пользователь {email} не найден")


async def list_all_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        print("\nВсе пользователи в БД:")
        for user in users:
            print(f"ID: {user.id}, Email: {user.email}, Active: {user.is_active}, Verified: {user.email_verified}")


async def main():
    # Показать всех пользователей
    await list_all_users()

    # Удалить конкретного
    await delete_user_by_email("nady.bessono@yandex.ru")
    await delete_user_by_email("gavriluklol228@gmail.com")
    await delete_user_by_email("gavriluklol227@gmail.com")

    # Показать результат
    await list_all_users()


if __name__ == "__main__":
    asyncio.run(main())