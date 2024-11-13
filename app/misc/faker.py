from faker import Faker


def create_headers():
    fake = Faker('ru_RU')
    fake_user_agent = fake.user_agent()
    return {
        "User-Agent": fake_user_agent
    }


HEADERS = create_headers()
