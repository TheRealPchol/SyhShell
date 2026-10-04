import os
import importlib.util

def call_function_from_file(file_path, function_name, *args, **kwargs):
    """Загружает модуль из файла и вызывает указанную функцию с сохранением globals."""
    # Извлекаем имя модуля из имени файла (без расширения .py)
    module_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # Создаем спецификацию модуля на основе пути к файлу
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load file from path: {file_path}")
        
    # Загружаем модуль в оперативную память
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Извлекаем нужную функцию из загруженного модуля
    if not hasattr(module, function_name):
        raise AttributeError(
            f"Function '{function_name}' not found in {file_path}"
        )
    target_function = getattr(module, function_name)
    
    # Вызываем функцию и передаем ей аргументы
    return target_function(*args, **kwargs)