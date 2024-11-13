import logging

import betterlogging as bl


def setup_logging():
    """
    Настройка конфигурации логирования для приложения.

    Этот метод инициализирует конфигурацию логирования для приложения.
    Устанавливает уровень логирования на INFO и настраивает базовый цветной лог для вывода.
    Формат лога включает имя файла, номер строки, уровень лога, временную метку, имя логгера и сообщение лога.

    Возвращает:
        None

    Пример использования:
        setup_logging()
    """
    log_level = logging.INFO
    bl.basic_colorized_config(level=log_level)

    logging.basicConfig(
        level=logging.INFO,
        format='%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s',
    )
    logger = logging.getLogger(__name__)
    logger.info('Запуск бэкенда')
