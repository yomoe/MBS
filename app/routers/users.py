import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.users import APIUserResponse, UserInfo, UserResponse
from app.users.dao import UserDAO

logger = logging.getLogger(__name__)
router_users = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
)


@router_users.post('/register', response_model=APIUserResponse, status_code=201)
async def add_new_user(user_info: UserInfo, session: AsyncSession = Depends(get_session)):
    logger.info(f'Получен запрос на добавление пользователя с ID {user_info.user_id}')
    existing_user = await UserDAO.find_one_or_none(user_id=user_info.user_id, session=session)

    if existing_user:
        # Проверяем, изменились ли данные пользователя
        fields_to_check = ['username', 'lastname', 'firstname']
        updated_fields = {
            field: getattr(user_info, field)
            for field in fields_to_check
            if getattr(existing_user, field) != getattr(user_info, field)
        }

        if updated_fields:
            # Обновляем данные пользователя
            try:
                updated_user = await UserDAO.update(session, {'user_id': user_info.user_id}, **updated_fields)
                return APIUserResponse(
                    status='updated',
                    message='Данные пользователя обновлены',
                    data=UserResponse(**updated_user.__dict__)
                )
            except Exception as e:
                logger.error(f"Не удалось обновить данные пользователя: {e}")
                raise HTTPException(status_code=500, detail="Не удалось добавить/обновить данные пользователя")
        # Если изменений нет
        return APIUserResponse(
            status='exists',
            message='Пользователь уже существует, обновлений не требуется',
            data=UserResponse(**existing_user.__dict__)
        )

    # Добавляем нового пользователя
    try:
        new_user = await UserDAO.add(session, **user_info.dict())
        return APIUserResponse(
            status='created',
            message='Пользователь успешно добавлен',
            data=UserResponse(**new_user.__dict__)
        )
    except Exception as e:
        logger.error(f"Не удалось добавить пользователя в базу данных: {e}")
        raise HTTPException(status_code=500, detail="Не удалось добавить/обновить данные пользователя")
