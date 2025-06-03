import clr
import os
import sys
import ctypes
import threading
import time
from collections import defaultdict, deque

hwtypes = ['Mainboard','SuperIO','CPU','RAM','GpuNvidia','GpuAti','TBalancer','Heatmaster','HDD']

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Перезапуск программы с правами администратора"""
    try:
        if is_admin():
            return True
        else:
            print("Запрос прав администратора...")
            # Получаем путь к текущему скрипту
            script_path = os.path.abspath(sys.argv[0])
            
            # Запускаем скрипт с правами администратора
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                sys.executable, 
                f'"{script_path}"', 
                None, 
                1
            )
            return False
    except Exception as e:
        print(f"Ошибка при запросе прав администратора: {e}")
        return False

def unblock_file(file_path):
    try:
        if not os.path.exists(file_path):
            print(f"Файл не найден: {file_path}")
            return False
            
        powershell_command = f'Unblock-File -Path "{file_path}"'
        result = os.system(f'powershell -Command "{powershell_command}"')
        if result != 0:
            print(f"Не удалось разблокировать файл {file_path}. Проверьте права доступа.")
            return False
        return True
    except Exception as e:
        print(f"Ошибка при разблокировке файла: {e}")
        return False

def initialize_openhardwaremonitor():
    try:
        # Попробуйте разные пути
        possible_paths = [
            rf'{os.getcwd()}\ohm\OpenHardwareMonitorLib.dll',
            rf'{os.getcwd()}\OpenHardwareMonitorLib.dll',
            r'.\ohm\OpenHardwareMonitorLib.dll',
            rf'{os.path.dirname(os.getcwd())}\ohm\OpenHardwareMonitorLib.dll'
        ]
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                print(f"Найден файл: {file_path}")
                break
        
        if not file_path:
            raise FileNotFoundError("OpenHardwareMonitorLib.dll не найдена ни в одном из путей")
            
        unblock_file(file_path)
        clr.AddReference(file_path)
        print("Библиотека успешно загружена")
        
        from OpenHardwareMonitor import Hardware
        print("Модуль Hardware импортирован")
        
        handle = Hardware.Computer()
        handle.MainboardEnabled = True
        handle.CPUEnabled = True
        handle.RAMEnabled = True
        handle.GPUEnabled = True
        handle.HDDEnabled = True
        handle.Open()
        print("Hardware Computer инициализирован")
        return handle
        
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        print(f"Тип ошибки: {type(e)}")
        raise

def fetch_stats(handle):
    for i in handle.Hardware:
        i.Update()
        for sensor in i.Sensors:
            parse_sensor(sensor)
        for j in i.SubHardware:
            j.Update()
            for subsensor in j.Sensors:
                parse_sensor(subsensor)

def parse_sensor(sensor):
    if sensor.Value and str(sensor.SensorType) == 'Temperature':
        temperature = float(sensor.Value)
        
        # Фильтруем некорректные значения (например, -13.5°C)
        if temperature > -10 and temperature < 150:
            result = u'{} {} Temperature Sensor #{} {} - {}\u00B0C'\
                    .format(hwtypes[sensor.Hardware.HardwareType], 
                            sensor.Hardware.Name, sensor.Index, 
                            sensor.Name, sensor.Value
                    )
            print(result)

def main():
    # Проверяем права администратора и запрашиваем их при необходимости
    if not run_as_admin():
        print("Перезапуск с правами администратора...")
        sys.exit(0)
    
    print("Инициализация OpenHardwareMonitor...")
    HardwareHandle = initialize_openhardwaremonitor()
    
    print("Запуск мониторинга температуры...")
    print("Нажмите Ctrl+C для завершения программы.")
    
    try:
        while True:
            fetch_stats(HardwareHandle)
            time.sleep(10)  # Обновление каждую секунду
            
    except KeyboardInterrupt:
        print("\nПрограмма прервана пользователем.")
    finally:
        print("Завершение работы...")

if __name__ == "__main__":
    main()