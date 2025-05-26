import asyncio
import logging
from asyncua import Server, ua
from datetime import datetime

class TemperatureOPCUAServer:
    def __init__(self, endpoint="opc.tcp://0.0.0.0:4840/freeopcua/server/"):
        self.server = Server()
        self.endpoint = endpoint
        self.namespace = "http://university.temperature.monitoring"
        self.nodes = {}
        self.is_started = False
        
    async def initialize(self):
        """Инициализация сервера"""
        await self.server.init()
        
        # Настройка сервера
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name("University Temperature Monitoring Server")
        
        # Настройка безопасности - разрешаем анонимный доступ
        self.server.set_security_policy([
            ua.SecurityPolicyType.NoSecurity,
        ])
        
        # Добавление пространства имен
        self.namespace_idx = await self.server.register_namespace(self.namespace)
        
        # Создание корневого объекта
        root_node = self.server.get_objects_node()
        
        # Создание объекта университета
        self.university_obj = await root_node.add_object(
            self.namespace_idx, "University"
        )
        
        # Создание структуры для тестирования
        await self.create_test_structure()
        
    async def create_test_structure(self):
        """Создание тестовой структуры узлов"""
        # Создаем несколько корпусов для тестирования
        for building_num in range(1, 4):  # Корпуса 1-3
            building_obj = await self.university_obj.add_object(
                self.namespace_idx, f"Building{building_num}"
            )
            
            # Создаем несколько аудиторий
            for room_num in [101, 102, 201, 301]:
                room_obj = await building_obj.add_object(
                    self.namespace_idx, f"Room{room_num}"
                )
                
                # Создаем несколько ПК
                for pc_num in range(1, 4):  # ПК 1-3
                    pc_obj = await room_obj.add_object(
                        self.namespace_idx, f"PC{pc_num}"
                    )
                    
                    # Создаем узлы для различных типов оборудования (включая реальные типы)
                    hardware_types = ["CPU", "RAM", "Mainboard", "GpuNvidia", "SuperIO", "HDD"]
                    
                    for hw_type in hardware_types:
                        hw_obj = await pc_obj.add_object(
                            self.namespace_idx, hw_type
                        )
                        
                        # Создаем узлы для различных типов датчиков
                        sensor_types = {
                            "CPU": ["CPU Core #1", "CPU Core #2", "CPU Core #3", "CPU Core #4", "CPU Package"],
                            "SuperIO": ["CPU Core", "Temperature #1", "Temperature #2", "Temperature #3"],
                            "GpuNvidia": ["GPU Core"],
                            "HDD": ["Temperature"],
                            "RAM": ["Memory"],
                            "Mainboard": ["System"]
                        }
                        
                        sensors = sensor_types.get(hw_type, ["Sensor0", "Sensor1"])
                        
                        for i, sensor_name in enumerate(sensors):
                            # Создаем объект для типа датчика
                            sensor_obj = await hw_obj.add_object(
                                self.namespace_idx, sensor_name.replace("#", "").replace(" ", "_")
                            )
                            
                            # Полный NodeID для датчика
                            full_node_id = f"Building{building_num}.Room{room_num}.PC{pc_num}.{hw_type}.{sensor_name}.Sensor{i}"
                            
                            # Создаем переменную для температуры с правильными параметрами
                            temp_var = await sensor_obj.add_variable(
                                self.namespace_idx,
                                f"Sensor{i}",
                                0.0,
                                ua.VariantType.Double
                            )
                            
                            # Делаем переменную записываемой (правильный способ)
                            await temp_var.set_writable(True)
                            
                            # Сохраняем ссылку на узел
                            self.nodes[full_node_id] = temp_var
                            
                        print(f"Создан узел типа {hw_type} с {len(sensors)} датчиками для Building{building_num}.Room{room_num}.PC{pc_num}")
    
    async def start(self):
        """Запуск сервера"""
        try:
            await self.server.start()
            self.is_started = True
            print(f"OPC UA сервер запущен: {self.endpoint}")
            print(f"Пространство имен: {self.namespace}")
            print(f"Создано узлов: {len(self.nodes)}")
        except Exception as e:
            print(f"Ошибка запуска сервера: {e}")
            self.is_started = False
            raise
        
    async def stop(self):
        """Остановка сервера"""
        if self.is_started and self.server:
            try:
                await self.server.stop()
                print("OPC UA сервер остановлен")
            except Exception as e:
                print(f"Ошибка при остановке сервера: {e}")
            finally:
                self.is_started = False
    
    async def monitor_changes(self):
        """Мониторинг изменений значений"""
        print("\nНачинаем мониторинг изменений температуры...")
        
        while self.is_started:
            try:
                changed_values = []
                
                # Проверяем изменения значений и выводим их
                for node_id, node in self.nodes.items():
                    try:
                        value = await node.read_value()
                        if value > 0:  # Показываем только ненулевые значения
                            changed_values.append((node_id, value))
                    except Exception:
                        pass  # Игнорируем ошибки чтения отдельных узлов
                
                # Выводим изменения
                if changed_values:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"\n[{timestamp}] Получены данные о температуре:")
                    for node_id, value in changed_values:
                        print(f"  {node_id}: {value:.1f}°C")
                        
                await asyncio.sleep(5)  # Проверяем каждые 5 секунд
                
            except asyncio.CancelledError:
                print("Мониторинг остановлен")
                break
            except Exception as e:
                print(f"Ошибка мониторинга: {e}")
                await asyncio.sleep(1)

async def main():
    # Настройка логирования
    logging.basicConfig(level=logging.WARNING)  # Уменьшаем количество логов
    
    # Создание и запуск сервера
    server = TemperatureOPCUAServer()
    
    try:
        print("Инициализация OPC UA сервера...")
        await server.initialize()
        
        print("Запуск сервера...")
        await server.start()
        
        print("\nСервер готов к приему данных!")
        print("Для остановки нажмите Ctrl+C")
        print(f"\nСписок созданных узлов ({len(server.nodes)} шт.):")
        for i, node_id in enumerate(list(server.nodes.keys())[:10]):  # Показываем первые 10
            print(f"  - {node_id}")
        if len(server.nodes) > 10:
            print(f"  ... и еще {len(server.nodes) - 10} узлов")
        
        # Запуск мониторинга изменений
        await server.monitor_changes()
        
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