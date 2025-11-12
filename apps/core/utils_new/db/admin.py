"""
Administrative Database Utilities

Handles superuser creation and database initialization tasks.
"""

import logging

logger = logging.getLogger("django")


def create_super_admin(db):
    """
    Create a superuser in the specified database.

    Prompts for required user details and creates superuser record.

    Args:
        db: Database alias to create user in

    Raises:
        ValueError: If database doesn't exist or invalid input provided
    """
    from apps.core.utils_new.db.connection import set_db_for_router

    try:
        set_db_for_router(db)
    except ValueError:
        logger.info("Database with this alias not exist operation can't be performed")
    else:
        logger.info(f"Creating SuperUser for {db}")
        from apps.peoples.models import People

        logger.info(
            "please provide required fields in this order single space separated\n"
        )
        logger.info(
            "loginid  password  peoplecode  peoplename  dateofbirth  dateofjoin  email"
        )
        inputs = input().split(" ")
        if len(inputs) == 7:
            user = People.objects.create_superuser(
                loginid=inputs[0],
                password=inputs[1],
                peoplecode=inputs[2],
                peoplename=inputs[3],
                dateofbirth=inputs[4],
                dateofjoin=inputs[5],
                email=inputs[6],
            )
            logger.info(
                f"Operation Successfull!\n Superuser with this loginid {user.loginid} is created"
            )
        else:
            raise ValueError("Please provide all fields!")


__all__ = [
    'create_super_admin',
]
