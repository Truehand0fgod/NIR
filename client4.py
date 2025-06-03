import clr
import os
import json
import asyncio
from asyncua import Client, ua
import time
import hashlib

# Расширенный список типов оборудования для большей универсальности
HARDWARE_TYPES = {
    0: 'Mainboard',
    1: 'SuperIO', 
    2: 'CPU',
    3: 'RAM',
    4: 'GpuNvidia',
    5: 'GpuAti',
    6: 'TBalancer',
    7: 'Heatmaster',
    8: 'HDD',
    9: 'SSD',
    10: 'Network'
}

UPDATE_INTERVAL = 10  # Интервал обновления в секундах

class TemperatureOPCUAClient:
    def __init__(self, config_path='config.json'):
        self.config = self.load_config(config_path)
        self.client = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.nodes = {}
        
    def load_config(self, config_path):
        """Загрузка конфигурации из JSON файла"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            # Создаем файл конфигурации по умолчанию
            default_config = {
                "opcua_server": {
                    "url": "opc.tcp://localhost:4840/freeopcua/server/",
                    "namespace": "http://university.temperature.monitoring",
                    "connection_timeout": 10,
                    "reconnect_interval": 5
                },
                "location": {
                    "building_number": 1,
                    "room_number": 101,
                    "pc_number": 1
                },
                "monitoring": {
                    "update_interval": 10,
                    "min_temperature_change": 0.5,
                    "max_sensor_failures": 10
                }
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            print(f"SUCCESS: Создан файл конфигурации {config_path}")
            return default_config
    
    def generate_node_id(self, building, room, pc, hardware_type, sensor_index):
        """Генерация NodeID (должна совпадать с серверной логикой)"""
        base_string = f"{building}.{room}.{pc}.{hardware_type}.{sensor_index}"
        hash_hex = hashlib.md5(base_string.encode()).hexdigest()[:8]
        node_id = int(hash_hex, 16) % 1000000
        return node_id
    
    async def connect(self):
        """Подключение к OPC UA серверу с обработкой переподключения"""
        try:
            if self.client:
                try:
                    await self.client.disconnect()
                except:
                    pass
                    
            self.client = Client(self.config['opcua_server']['url'])
            
            # Настройка безопасности и таймаутов
            self.client.set_security_string("None")
            
            # Установка таймаутов
            timeout = self.config['opcua_server'].get('connection_timeout', 10)
            self.client.session_timeout = timeout * 1000  # в миллисекундах
            
            await self.client.connect()
            self.connected = True
            self.reconnect_attempts = 0
            
            print(f"SUCCESS: Подключен к OPC UA серверу: {self.config['opcua_server']['url']}")
            return True
            
        except Exception as e:
            self.connected = False
            self.reconnect_attempts += 1
            print(f"ERROR: Ошибка подключения к OPC UA серверу (попытка {self.reconnect_attempts}): {e}")
            
            if self.reconnect_attempts < self.max_reconnect_attempts:
                reconnect_interval = self.config['opcua_server'].get('reconnect_interval', 5)
                print(f"INFO: Повторная попытка подключения через {reconnect_interval} секунд...")
                await asyncio.sleep(reconnect_interval)
                return await self.connect()
            else:
                print(f"CRITICAL: Превышено максимальное количество попыток подключения ({self.max_reconnect_attempts})")
                return False
    
    async def disconnect(self):
        """Отключение от OPC UA сервера"""
        if self.client and self.connected:
            try:
                await self.client.disconnect()
                self.connected = False
                print("SUCCESS: Отключен от OPC UA сервера")
            except Exception as e:
                print(f"WARNING: Ошибка при отключении: {e}")
    
    async def send_temperature_data(self, sensor_data):
        """Отправка данных температуры на сервер"""
        if not self.connected:
            print("ERROR: Нет подключения к серверу")
            return False
            
        successful_sends = 0
        failed_sends = 0
        
        print(f"INFO: Обработка {len(sensor_data)} датчиков...")
        
        # Получаем пространство имен
        try:
            namespace_idx = await self.client.get_namespace_index(
                self.config['opcua_server']['namespace']
            )
        except Exception as e:
            print(f"ERROR: Ошибка получения пространства имен: {e}")
            return False
        
        building = self.config['location']['building_number']
        room = self.config['location']['room_number']  
        pc = self.config['location']['pc_number']
        
        for sensor_info in sensor_data:
            try:
                # Генерируем NodeID
                node_id = self.generate_node_id(
                    building, room, pc, 
                    sensor_info['hardware_type'], 
                    sensor_info['sensor_index']
                )
                
                # Создаем NodeId объект
                node = ua.NodeId(node_id, namespace_idx)
                
                # Получаем узел и записываем значение
                var = self.client.get_node(node)
                await var.write_value(sensor_info['temperature'])
                
                print(f"SUCCESS: {sensor_info['temperature']:.1f}°C -> {sensor_info['hardware_name']} {sensor_info['sensor_name']} (ID: {node_id})")
                successful_sends += 1
                
            except Exception as e:
                print(f"ERROR: Ошибка отправки для {sensor_info['sensor_name']}: {e}")
                failed_sends += 1
        
        success_rate = (successful_sends / len(sensor_data)) * 100 if sensor_data else 0
        print(f"RESULT: Итого: {successful_sends}/{len(sensor_data)} ({success_rate:.1f}%) успешно отправлено")
        
        # Если много ошибок, возможно проблема с подключением
        if failed_sends > successful_sends and failed_sends > 3:
            print("WARNING: Высокий процент ошибок, проверяем подключение...")
            self.connected = False
            
        return successful_sends > 0

def unblock_file(file_path):
    """Разблокировка DLL файла в Windows"""
    try:
        if os.name == 'nt':  # Windows
            powershell_command = f'Unblock-File -Path "{file_path}"'
            result = os.system(f'powershell -Command "{powershell_command}"')
            if result != 0:
                print(f"WARNING: Не удалось разблокировать файл {file_path}")
    except Exception as e:
        print(f"WARNING: Ошибка при разблокировке файла: {e}")

def initialize_openhardwaremonitor():
    """Инициализация библиотеки OpenHardwareMonitor"""
    try:
        file = rf'{os.getcwd()}\ohm\OpenHardwareMonitorLib.dll'
        
        # Проверяем существование файла
        if not os.path.exists(file):
            print(f"ERROR: Файл не найден: {file}")
            print("INFO: Убедитесь что папка 'ohm' с библиотекой OpenHardwareMonitorLib.dll находится в текущей директории")
            return None
            
        unblock_file(file)
        clr.AddReference(file)

        from OpenHardwareMonitor import Hardware

        handle = Hardware.Computer()
        handle.MainboardEnabled = True
        handle.CPUEnabled = True
        handle.RAMEnabled = True
        handle.GPUEnabled = True
        handle.HDDEnabled = True
        handle.Open()
        
        print("SUCCESS: OpenHardwareMonitor инициализирован")
        return handle
        
    except Exception as e:
        print(f"ERROR: Ошибка инициализации OpenHardwareMonitor: {e}")
        return None

def fetch_stats(handle):
    """Получение данных с датчиков температуры"""
    if not handle:
        return []
        
    sensor_data = []
    
    try:
        for i in handle.Hardware:
            i.Update()
            
            # Обработка основных датчиков
            for sensor in i.Sensors:
                if sensor.Value and str(sensor.SensorType) == 'Temperature':
                    hw_type_num = int(sensor.Hardware.HardwareType)
                    hw_type = HARDWARE_TYPES.get(hw_type_num, f'Unknown{hw_type_num}')
                    
                    sensor_info = {
                        'hardware_type': hw_type,
                        'hardware_name': sensor.Hardware.Name,
                        'sensor_index': sensor.Index,
                        'sensor_name': sensor.Name,
                        'temperature': float(sensor.Value)
                    }
                    sensor_data.append(sensor_info)
                    
                    print(f"SENSOR: {hw_type} {sensor.Hardware.Name} - {sensor.Name}: {sensor.Value:.1f}°C")
            
            # Обработка подчиненных устройств (например, отдельные ядра CPU)
            for j in i.SubHardware:
                j.Update()
                for subsensor in j.Sensors:
                    if subsensor.Value and str(subsensor.SensorType) == 'Temperature':
                        hw_type_num = int(subsensor.Hardware.HardwareType)
                        hw_type = HARDWARE_TYPES.get(hw_type_num, f'Unknown{hw_type_num}')
                        
                        sensor_info = {
                            'hardware_type': hw_type,
                            'hardware_name': subsensor.Hardware.Name,
                            'sensor_index': subsensor.Index,
                            'sensor_name': subsensor.Name,
                            'temperature': float(subsensor.Value)
                        }
                        sensor_data.append(sensor_info)
                        
                        print(f"SENSOR: {hw_type} {subsensor.Hardware.Name} - {subsensor.Name}: {subsensor.Value:.1f}°C")
    
    except Exception as e:
        print(f"ERROR: Ошибка при сборе данных с датчиков: {e}")
    
    return sensor_data

async def main():
    print("STARTING: Запуск универсального клиента мониторинга температуры")
    print("=" * 60)
    
    # Инициализация мониторинга оборудования
    print("INIT: Инициализация мониторин")

    hardware = initialize_openhardwaremonitor()
    if not hardware:
        print("CRITICAL: Не удалось инициализировать мониторинг оборудования")
        return
    
    # Инициализация OPC UA клиента
    print("INIT: Инициализация OPC UA клиента...")
    opcua_client = TemperatureOPCUAClient()
    
    # Подключение к серверу
    print("CONNECT: Подключение к OPC UA серверу...")
    if not await opcua_client.connect():
        print("CRITICAL: Не удалось подключиться к OPC UA серверу")
        return
    
    try:
        print("INFO: Начинаем мониторинг температуры...")
        print(f"INFO: Интервал обновления: {UPDATE_INTERVAL} секунд")
        print("INFO: Для остановки нажмите Ctrl+C")
        print("=" * 60)
        
        iteration = 0
        
        while True:
            iteration += 1
            print(f"\nITERATION: Цикл #{iteration} - {time.strftime('%H:%M:%S')}")
            
            # Сбор данных с датчиков
            print("COLLECT: Сбор данных с датчиков...")
            sensor_data = fetch_stats(hardware)
            
            if sensor_data:
                print(f"INFO: Найдено {len(sensor_data)} датчиков температуры")
                
                # Отправка данных на сервер
                print("SEND: Отправка данных на OPC UA сервер...")
                success = await opcua_client.send_temperature_data(sensor_data)
                
                if not success:
                    print("WARNING: Ошибка отправки данных, попытка переподключения...")
                    if not await opcua_client.connect():
                        print("ERROR: Не удалось переподключиться к серверу")
                        break
            else:
                print("WARNING: Не найдено активных датчиков температуры")
            
            print(f"WAIT: Ожидание {UPDATE_INTERVAL} секунд до следующего обновления...")
            await asyncio.sleep(UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nSTOP: Получен сигнал остановки от пользователя")
        
    except Exception as e:
        print(f"\nERROR: Критическая ошибка в основном цикле: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Очистка ресурсов
        print("CLEANUP: Завершение работы...")
        
        # Отключение от OPC UA сервера
        await opcua_client.disconnect()
        
        # Закрытие мониторинга оборудования
        if hardware:
            try:
                hardware.Close()
                print("SUCCESS: Мониторинг оборудования закрыт")
            except Exception as e:
                print(f"WARNING: Ошибка при закрытии мониторинга: {e}")
        
        print("SUCCESS: Клиент завершен")

if __name__ == "__main__":
    asyncio.run(main())