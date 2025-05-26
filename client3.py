import clr
import os
import json
import asyncio
from asyncua import Client
import time

hwtypes = ['Mainboard','SuperIO','CPU','RAM','GpuNvidia','GpuAti','TBalancer','Heatmaster','HDD']

class TemperatureOPCUAClient:
    def __init__(self, config_path='config.json'):
        self.config = self.load_config(config_path)
        self.client = None
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
                    "namespace": "http://university.temperature.monitoring"
                },
                "location": {
                    "building_number": 1,
                    "room_number": 101,
                    "pc_number": 1
                },
                "update_interval": 5
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            print(f"Создан файл конфигурации {config_path}. Пожалуйста, укажите ваше местоположение.")
            return default_config
    
    def generate_node_id(self, sensor_info):
        """Генерация NodeID на основе местоположения и информации о датчике"""
        building = self.config['location']['building_number']
        room = self.config['location']['room_number']
        pc = self.config['location']['pc_number']
        
        # Формат: Building.Room.PC.HardwareType.SensorIndex
        node_id = f"Building{building}.Room{room}.PC{pc}.{sensor_info['hardware_type']}.{sensor_info['sensor_name']}.Sensor{sensor_info['sensor_index']}"
        return node_id
    
    async def connect(self):
        """Подключение к OPC UA серверу"""
        try:
            self.client = Client(self.config['opcua_server']['url'])
            
            # Настройка безопасности
            self.client.set_security_string("None")
            
            await self.client.connect()
            print(f"Подключен к OPC UA серверу: {self.config['opcua_server']['url']}")
            return True
        except Exception as e:
            print(f"Ошибка подключения к OPC UA серверу: {e}")
            return False
    
    async def disconnect(self):
        """Отключение от OPC UA сервера"""
        if self.client:
            await self.client.disconnect()
            print("Отключен от OPC UA сервера")
    
    async def create_or_get_node(self, node_id):
        """Создание или получение узла на сервере"""
        try:
            # Получаем пространство имен
            namespace_idx = await self.client.get_namespace_index(self.config['opcua_server']['namespace'])
            
            # Создаем NodeId - ищем узел через путь в дереве объектов
            # Разбираем node_id на части
            parts = node_id.split('.')
            if len(parts) < 6:
                print(f"Неверный формат node_id: {node_id}")
                return None
                
            building_part = parts[0]  # Building1
            room_part = parts[1]      # Room101
            pc_part = parts[2]        # PC1
            hw_type = parts[3]        # CPU, SuperIO, etc.
            sensor_name = parts[4]    # CPU Core #1, Temperature #1, etc.
            sensor_idx = parts[5]     # Sensor0, Sensor1, etc.
            
            # Строим путь к узлу
            objects_node = self.client.get_objects_node()
            university_node = await objects_node.get_child([f"{namespace_idx}:University"])
            building_node = await university_node.get_child([f"{namespace_idx}:{building_part}"])
            room_node = await building_node.get_child([f"{namespace_idx}:{room_part}"])
            pc_node = await room_node.get_child([f"{namespace_idx}:{pc_part}"])
            hw_node = await pc_node.get_child([f"{namespace_idx}:{hw_type}"])
            
            # Преобразуем имя датчика для поиска (убираем # и пробелы)
            sensor_name_clean = sensor_name.replace("#", "").replace(" ", "_")
            sensor_type_node = await hw_node.get_child([f"{namespace_idx}:{sensor_name_clean}"])
            
            # Получаем переменную температуры
            temp_var = await sensor_type_node.get_child([f"{namespace_idx}:{sensor_idx}"])
            
            return temp_var
                
        except Exception as e:
            print(f"Ошибка при поиске узла {node_id}: {e}")
            return None
    
    async def send_temperature_data(self, sensor_data):
        """Отправка данных температуры на сервер"""
        successful_sends = 0
        
        print(f"Обработка {len(sensor_data)} датчиков...")
        
        for sensor_info in sensor_data:
            node_id = self.generate_node_id(sensor_info)
            
            if node_id not in self.nodes:
                print(f"Поиск узла: {node_id}")
                node = await self.create_or_get_node(node_id)
                if node:
                    self.nodes[node_id] = node
                    print(f"✓ Узел найден и кэширован")
                else:
                    print(f"✗ Узел не найден: {node_id}")
                    continue
            
            try:
                # Отправляем значение температуры
                await self.nodes[node_id].write_value(sensor_info['temperature'])
                print(f"✓ Отправлено: {sensor_info['temperature']:.1f}°C -> {sensor_info['hardware_name']} {sensor_info['sensor_name']}")
                successful_sends += 1
            except Exception as e:
                print(f"✗ Ошибка отправки для {node_id}: {e}")
        
        print(f"Итого успешно отправлено: {successful_sends}/{len(sensor_data)} значений")

def unblock_file(file_path):
    try:
        powershell_command = f'Unblock-File -Path "{file_path}"'
        result = os.system(f'powershell -Command "{powershell_command}"')
        if result != 0:
            print(f"Не удалось разблокировать файл {file_path}. Проверьте права доступа.")
    except Exception as e:
        print(f"Ошибка при разблокировке файла: {e}")

def initialize_openhardwaremonitor():
    file = rf'{os.getcwd()}\ohm\OpenHardwareMonitorLib.dll'
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
    return handle

def fetch_stats(handle):
    """Получение данных с датчиков температуры"""
    sensor_data = []
    
    for i in handle.Hardware:
        i.Update()
        for sensor in i.Sensors:
            if sensor.Value and str(sensor.SensorType) == 'Temperature':
                sensor_info = {
                    'hardware_type': hwtypes[sensor.Hardware.HardwareType],
                    'hardware_name': sensor.Hardware.Name,
                    'sensor_index': sensor.Index,
                    'sensor_name': sensor.Name,
                    'temperature': float(sensor.Value)
                }
                sensor_data.append(sensor_info)
                
                result = u'{} {} Temperature Sensor #{} {} - {}°C'\
                        .format(sensor_info['hardware_type'], 
                                sensor_info['hardware_name'], 
                                sensor_info['sensor_index'], 
                                sensor_info['sensor_name'], 
                                sensor_info['temperature']
                        )
                print(result)
        
        for j in i.SubHardware:
            j.Update()
            for subsensor in j.Sensors:
                if subsensor.Value and str(subsensor.SensorType) == 'Temperature':
                    sensor_info = {
                        'hardware_type': hwtypes[subsensor.Hardware.HardwareType],
                        'hardware_name': subsensor.Hardware.Name,
                        'sensor_index': subsensor.Index,
                        'sensor_name': subsensor.Name,
                        'temperature': float(subsensor.Value)
                    }
                    sensor_data.append(sensor_info)
                    
                    result = u'{} {} Temperature Sensor #{} {} - {}°C'\
                            .format(sensor_info['hardware_type'], 
                                    sensor_info['hardware_name'], 
                                    sensor_info['sensor_index'], 
                                    sensor_info['sensor_name'], 
                                    sensor_info['temperature']
                            )
                    print(result)
    
    return sensor_data

async def main():
    # Инициализация мониторинга оборудования
    hardware_handle = initialize_openhardwaremonitor()
    
    # Инициализация OPC UA клиента
    opcua_client = TemperatureOPCUAClient()
    
    # Подключение к серверу
    if not await opcua_client.connect():
        print("Не удалось подключиться к OPC UA серверу")
        return
    
    try:
        while True:
            print("\n" + "="*50)
            print("Сбор данных с датчиков температуры...")
            
            # Получение данных с датчиков
            sensor_data = fetch_stats(hardware_handle)
            
            # Отправка данных на OPC UA сервер
            if sensor_data:
                print("\nОтправка данных на OPC UA сервер...")
                await opcua_client.send_temperature_data(sensor_data)
            else:
                print("Датчики температуры не найдены")
            
            # Ожидание перед следующим циклом
            await asyncio.sleep(opcua_client.config['update_interval'])
            
    except KeyboardInterrupt:
        print("\nОстановка программы...")
    finally:
        await opcua_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())