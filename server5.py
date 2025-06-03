import asyncio
import logging
from asyncua import Server, ua
from datetime import datetime
import hashlib

class TemperatureOPCUAServer:
    def __init__(self, endpoint="opc.tcp://0.0.0.0:4840/freeopcua/server/"):
        self.server = Server()
        self.endpoint = endpoint
        self.namespace = "http://university.temperature.monitoring"
        self.nodes = {}  # Хранилище созданных узлов: {node_id: node_object}
        self.node_info = {}  # Информация о узлах: {node_id: {metadata}}
        self.is_started = False
        
    async def initialize(self):
        """Инициализация сервера"""
        await self.server.init()
        
        # Настройка сервера
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name("Universal Temperature Monitoring Server")
        
        # Настройка безопасности
        self.server.set_security_policy([
            ua.SecurityPolicyType.NoSecurity,
        ])
        
        # Добавление пространства имен
        self.namespace_idx = await self.server.register_namespace(self.namespace)
        
        # Создание корневого объекта
        root_node = self.server.get_objects_node()
        self.sensors_root = await root_node.add_object(
            self.namespace_idx, "TemperatureSensors"
        )
        
        # ВАЖНО: Регистрируем обработчик для динамического создания узлов
        await self._setup_dynamic_node_creation()
        
        print("Сервер инициализирован и готов к динамическому созданию узлов")
        
    async def _setup_dynamic_node_creation(self):
        """Настройка динамического создания узлов при записи"""
        # Создаем предварительно все возможные узлы для типичных конфигураций
        # Это временное решение для демонстрации
        print("INFO: Создание узлов для динамического принятия данных...")
        
        # Создаем узлы для нескольких типичных конфигураций ПК
        # Поддерживаем несколько зданий, комнат и ПК
        for building in range(1, 5):  # Здания 1-4
            for room in range(100, 110):  # Комнаты 100-109
                for pc in range(1, 6):  # ПК 1-5
                    # Создаем типичные узлы для каждого ПК
                    await self._create_typical_nodes_for_pc(building, room, pc)
        
    async def _create_typical_nodes_for_pc(self, building, room, pc):
        """Создание типичных узлов для ПК"""
        # Типичные конфигурации датчиков
        typical_sensors = [
            # CPU датчики (обычно 0-10 индексов)
            ("CPU", 0, "CPU Core #1"),
            ("CPU", 1, "CPU Core #2"),
            ("CPU", 2, "CPU Core #3"),
            ("CPU", 3, "CPU Core #4"),
            ("CPU", 4, "CPU Package"),
            ("CPU", 5, "CPU Core #5"),
            ("CPU", 6, "CPU Core #6"),
            ("CPU", 7, "CPU Core #7"),
            ("CPU", 8, "CPU Core #8"),
            
            # SuperIO датчики (обычно 0-10 индексов)
            ("SuperIO", 0, "CPU Core"),
            ("SuperIO", 1, "Temperature #1"),
            ("SuperIO", 2, "Temperature #2"),
            ("SuperIO", 3, "Temperature #3"),
            ("SuperIO", 4, "Temperature #4"),
            ("SuperIO", 5, "Temperature #5"),
            
            # GPU датчики
            ("GpuNvidia", 0, "GPU Core"),
            ("GpuAti", 0, "GPU Core"),
            
            # Диски
            ("HDD", 0, "Temperature"),
            ("HDD", 1, "Temperature"),
            ("HDD", 2, "Temperature"),
            ("SSD", 0, "Temperature"),
            ("SSD", 1, "Temperature"),
        ]
        
        for hw_type, sensor_idx, sensor_name in typical_sensors:
            node_id, _ = self.generate_node_id(building, room, pc, hw_type, sensor_idx)
            
            if node_id not in self.nodes:
                try:
                    display_name = f"B{building}_R{room}_P{pc}_{hw_type}_{sensor_idx}"
                    
                    temp_var = await self.sensors_root.add_variable(
                        ua.NodeId(node_id, self.namespace_idx),
                        display_name,
                        0.0,
                        ua.VariantType.Double
                    )
                    
                    await temp_var.set_writable(True)
                    
                    self.nodes[node_id] = temp_var
                    self.node_info[node_id] = {
                        'building': building,
                        'room': room,
                        'pc': pc,
                        'hardware_type': hw_type,
                        'hardware_name': 'Unknown',
                        'sensor_index': sensor_idx,
                        'sensor_name': sensor_name,
                        'display_name': display_name,
                        'created_at': datetime.now()
                    }
                except:
                    pass  # Игнорируем ошибки создания отдельных узлов
        
    def generate_node_id(self, building, room, pc, hardware_type, sensor_index):
        """Генерация числового NodeID на основе местоположения и индекса датчика"""
        # Создаем уникальный строковый идентификатор
        base_string = f"{building}.{room}.{pc}.{hardware_type}.{sensor_index}"
        
        # Генерируем числовой ID из хеша (берем первые 8 символов и конвертируем в int)
        hash_hex = hashlib.md5(base_string.encode()).hexdigest()[:8]
        node_id = int(hash_hex, 16) % 1000000  # Ограничиваем размер числа
        
        return node_id, base_string
        
    async def create_sensor_node(self, building, room, pc, hardware_type, hardware_name, sensor_index, sensor_name):
        """Динамическое создание узла датчика"""
        node_id, base_string = self.generate_node_id(building, room, pc, hardware_type, sensor_index)
        
        if node_id in self.nodes:
            # Обновляем метаданные если узел уже существует
            if hardware_name != 'Unknown':
                self.node_info[node_id]['hardware_name'] = hardware_name
                self.node_info[node_id]['sensor_name'] = sensor_name
            return self.nodes[node_id]
            
        try:
            # Создаем переменную для температуры напрямую в корневом объекте датчиков
            display_name = f"B{building}_R{room}_P{pc}_{hardware_type}_{sensor_index}"
            
            temp_var = await self.sensors_root.add_variable(
                ua.NodeId(node_id, self.namespace_idx),
                display_name,
                0.0,
                ua.VariantType.Double
            )
            
            # Делаем переменную записываемой
            await temp_var.set_writable(True)
            
            # Сохраняем узел и его метаданные
            self.nodes[node_id] = temp_var
            self.node_info[node_id] = {
                'building': building,
                'room': room,
                'pc': pc,
                'hardware_type': hardware_type,
                'hardware_name': hardware_name,
                'sensor_index': sensor_index,
                'sensor_name': sensor_name,
                'base_string': base_string,
                'display_name': display_name,
                'created_at': datetime.now()
            }
            
            print(f"SUCCESS: Создан узел {node_id} ({display_name}) для {hardware_name} - {sensor_name}")
            return temp_var
            
        except Exception as e:
            print(f"ERROR: Ошибка создания узла {node_id}: {e}")
            return None
    
    async def get_or_create_node(self, building, room, pc, hardware_type, hardware_name, sensor_index, sensor_name):
        """Получение существующего или создание нового узла"""
        node_id, _ = self.generate_node_id(building, room, pc, hardware_type, sensor_index)
        
        if node_id in self.nodes:
            # Обновляем метаданные если нужно
            if hardware_name != 'Unknown' and self.node_info[node_id]['hardware_name'] == 'Unknown':
                self.node_info[node_id]['hardware_name'] = hardware_name
                self.node_info[node_id]['sensor_name'] = sensor_name
            return self.nodes[node_id]
        else:
            return await self.create_sensor_node(building, room, pc, hardware_type, hardware_name, sensor_index, sensor_name)
    
    async def start(self):
        """Запуск сервера"""
        try:
            await self.server.start()
            self.is_started = True
            print(f"SUCCESS: OPC UA сервер запущен: {self.endpoint}")
            print(f"SUCCESS: Пространство имен: {self.namespace}")
            print(f"SUCCESS: Режим работы: динамическое создание узлов")
            print(f"INFO: Предварительно создано узлов: {len(self.nodes)}")
            print(f"INFO: Поддерживаемые конфигурации:")
            print(f"      - Здания: 1-4")
            print(f"      - Комнаты: 100-109")
            print(f"      - ПК: 1-5")
            
        except Exception as e:
            print(f"ERROR: Ошибка запуска сервера: {e}")
            self.is_started = False
            raise
    
    async def stop(self):
        """Остановка сервера"""
        if self.is_started and self.server:
            try:
                await self.server.stop()
                print("SUCCESS: OPC UA сервер остановлен")
            except Exception as e:
                print(f"ERROR: Ошибка при остановке сервера: {e}")
            finally:
                self.is_started = False
    
    async def update_temperature(self, building, room, pc, hardware_type, hardware_name, sensor_index, sensor_name, temperature):
        """Обновление значения температуры (создает узел если не существует)"""
        try:
            node = await self.get_or_create_node(building, room, pc, hardware_type, hardware_name, sensor_index, sensor_name)
            if node:
                await node.write_value(float(temperature))
                return True
            return False
        except Exception as e:
            print(f"ERROR: Ошибка обновления температуры: {e}")
            return False
    
    async def monitor_changes(self):
        """Мониторинг изменений значений"""
        print("\nMONITOR: Начинаем мониторинг изменений температуры...")
        
        last_values = {}  # Для отслеживания изменений
        
        while self.is_started:
            try:
                current_values = {}
                changed_values = []
                
                # Проверяем все созданные узлы
                for node_id, node in self.nodes.items():
                    try:
                        value = await node.read_value()
                        current_values[node_id] = value
                        
                        # Проверяем изменения (показываем только изменившиеся значения)
                        if node_id not in last_values or abs(last_values[node_id] - value) > 0.1:
                            if value > 0:  # Показываем только ненулевые значения
                                info = self.node_info[node_id]
                                changed_values.append((node_id, value, info))
                                
                    except Exception:
                        pass  # Игнорируем ошибки чтения отдельных узлов
                
                # Выводим изменения
                if changed_values:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"\nUPDATE: [{timestamp}] Обновления температуры:")
                    for node_id, value, info in changed_values:
                        print(f"   TEMP: {info['display_name']}: {value:.1f}°C")
                        if info['hardware_name'] != 'Unknown':
                            print(f"      ({info['hardware_name']} - {info['sensor_name']})")
                
                last_values = current_values
                await asyncio.sleep(3)  # Проверяем каждые 3 секунды
                
            except asyncio.CancelledError:
                print("STOP: Мониторинг остановлен")
                break
            except Exception as e:
                print(f"ERROR: Ошибка мониторинга: {e}")
                await asyncio.sleep(1)
    
    def print_status(self):
        """Вывод статуса сервера"""
        if self.nodes:
            print(f"\nSTATUS: Статус сервера:")
            print(f"   • Активных узлов: {len(self.nodes)}")
            
            # Группировка по компьютерам
            computers = {}
            active_computers = 0
            for node_id, info in self.node_info.items():
                # Проверяем, был ли узел активен (значение > 0)
                try:
                    value = asyncio.run_coroutine_threadsafe(
                        self.nodes[node_id].read_value(), 
                        asyncio.get_event_loop()
                    ).result(timeout=0.1)
                    if value > 0:
                        comp_key = f"B{info['building']}_R{info['room']}_P{info['pc']}"
                        if comp_key not in computers:
                            computers[comp_key] = []
                            active_computers += 1
                        computers[comp_key].append(info)
                except:
                    pass
            
            print(f"   • Активных ПК: {active_computers}")
            for comp, sensors in computers.items():
                hw_types = set(s['hardware_type'] for s in sensors)
                active_sensors = [s for s in sensors if s['hardware_name'] != 'Unknown']
                print(f"     - {comp}: {len(active_sensors)} активных датчиков ({', '.join(hw_types)})")

async def main():
    # Настройка логирования
    logging.basicConfig(level=logging.WARNING)
    
    # Создание и запуск сервера
    server = TemperatureOPCUAServer()
    
    try:
        print("Инициализация универсального OPC UA сервера...")
        await server.initialize()
        
        print("Запуск сервера...")
        await server.start()
        
        print("\n Сервер готов к приему данных!")
        
        # Создаем задачи для мониторинга и статуса
        monitor_task = asyncio.create_task(server.monitor_changes())
        
        # Периодический вывод статуса
        # async def status_reporter():
        #     while server.is_started:
        #         await asyncio.sleep(30)  # Каждые 30 секунд
        #         server.print_status()
        
        # status_task = asyncio.create_task(status_reporter())
        
        # Ждем завершения
        await asyncio.gather(monitor_task)
         
    except KeyboardInterrupt:
        print("\n\nПолучен сигнал остановки...")
    except Exception as e:
        print(f"Критическая ошибка сервера: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Остановка сервера...")
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())