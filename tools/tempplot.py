import clr
import os
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import datetime, timedelta
import threading
import time
from collections import defaultdict, deque

hwtypes = ['Mainboard','SuperIO','CPU','RAM','GpuNvidia','GpuAti','TBalancer','Heatmaster','HDD']

class TemperatureMonitor:
    def __init__(self, max_points=100):
        self.max_points = max_points
        self.data = defaultdict(lambda: {'times': deque(maxlen=max_points), 'temps': deque(maxlen=max_points)})
        self.start_time = datetime.now()
        self.lock = threading.Lock()
        self.running = True
        
    def add_data_point(self, sensor_name, temperature):
        with self.lock:
            current_time = datetime.now()
            elapsed_seconds = (current_time - self.start_time).total_seconds()
            
            self.data[sensor_name]['times'].append(elapsed_seconds)
            self.data[sensor_name]['temps'].append(temperature)
    
    def get_data_copy(self):
        with self.lock:
            return {name: {'times': list(info['times']), 'temps': list(info['temps'])} 
                   for name, info in self.data.items()}

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

def fetch_stats(handle, monitor):
    for i in handle.Hardware:
        i.Update()
        for sensor in i.Sensors:
            parse_sensor(sensor, monitor)
        for j in i.SubHardware:
            j.Update()
            for subsensor in j.Sensors:
                parse_sensor(subsensor, monitor)

def parse_sensor(sensor, monitor):
    if sensor.Value and str(sensor.SensorType) == 'Temperature':
        # Создаем уникальное имя для датчика
        sensor_name = f"{hwtypes[sensor.Hardware.HardwareType]} {sensor.Hardware.Name} - {sensor.Name}"
        temperature = float(sensor.Value)
        
        # Фильтруем некорректные значения (например, -13.5°C)
        if temperature > -10 and temperature < 100:
            monitor.add_data_point(sensor_name, temperature)
            
        result = u'{} {} Temperature Sensor #{} {} - {}\u00B0C'\
                .format(hwtypes[sensor.Hardware.HardwareType], 
                        sensor.Hardware.Name, sensor.Index, 
                        sensor.Name, sensor.Value
                )
        print(result)

def data_collection_thread(handle, monitor, interval=1.0):
    """Поток для сбора данных с датчиков"""
    while monitor.running:
        try:
            fetch_stats(handle, monitor)
            time.sleep(interval)
        except Exception as e:
            print(f"Ошибка при сборе данных: {e}")
            time.sleep(interval)

def setup_plot():
    """Настройка графика"""
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlabel('Время (секунды)')
    ax.set_ylabel('Температура (°C)')
    ax.set_title('Мониторинг температуры датчиков в реальном времени')
    ax.grid(True, alpha=0.3)
    
    return fig, ax

def animate(frame, ax, monitor):
    """Функция анимации для обновления графика"""
    ax.clear()
    ax.set_xlabel('Время (секунды)')
    ax.set_ylabel('Температура (°C)')
    ax.set_title('Мониторинг температуры датчиков в реальном времени')
    ax.grid(True, alpha=0.3)
    
    data_copy = monitor.get_data_copy()
    
    # Цвета для разных типов датчиков
    colors = {
        'CPU': ['#ff6b6b', '#ff8e53', '#ff6b35'],
        'GPU': ['#4ecdc4', '#45b7aa'],
        'SuperIO': ['#95e1d3', '#a8e6cf', '#88d8c0'],
        'HDD': ['#fce38a', '#f38ba8']
    }
    
    color_idx = 0
    all_colors = ['#ff6b6b', '#4ecdc4', '#95e1d3', '#fce38a', '#ff8e53', '#45b7aa', '#a8e6cf', '#f38ba8']
    
    for sensor_name, sensor_data in data_copy.items():
        if len(sensor_data['times']) > 1:
            # Определяем цвет по типу датчика
            sensor_color = all_colors[color_idx % len(all_colors)]
            color_idx += 1
            
            # Сокращаем имя датчика для легенды
            short_name = sensor_name.split(' - ')[-1]
            if 'CPU' in sensor_name:
                short_name = f"CPU: {short_name}"
            elif 'GPU' in sensor_name:
                short_name = f"GPU: {short_name}"
            elif 'HDD' in sensor_name:
                short_name = f"HDD: {short_name.split()[-1] if len(short_name.split()) > 1 else short_name}"
            
            ax.plot(sensor_data['times'], sensor_data['temps'], 
                   label=short_name, linewidth=2, color=sensor_color, alpha=0.8)
    
    if data_copy:
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
        # Автоматическое масштабирование оси Y с небольшими отступами
        all_temps = []
        for sensor_data in data_copy.values():
            all_temps.extend(sensor_data['temps'])
        
        if all_temps:
            min_temp = min(all_temps) - 5
            max_temp = max(all_temps) + 5
            ax.set_ylim(min_temp, max_temp)
    
    plt.tight_layout()

def main():
    print("Инициализация OpenHardwareMonitor...")
    HardwareHandle = initialize_openhardwaremonitor()
    
    print("Создание монитора температуры...")
    monitor = TemperatureMonitor(max_points=200)  # Храним последние 200 точек
    
    print("Запуск сбора данных...")
    # Запускаем поток для сбора данных
    data_thread = threading.Thread(target=data_collection_thread, 
                                 args=(HardwareHandle, monitor, 0.5))  # Обновление каждые 0.5 сек
    data_thread.daemon = True
    data_thread.start()
    
    # Даем время для сбора первых данных
    time.sleep(2)
    
    print("Запуск графика...")
    print("Закройте окно графика для завершения программы.")
    
    # Настройка и запуск графика
    fig, ax = setup_plot()
    
    try:
        # Анимация обновляется каждые 1000мс (1 секунда)
        ani = animation.FuncAnimation(fig, animate, fargs=(ax, monitor), 
                                    interval=1000, blit=False, cache_frame_data=False)
        
        plt.show()
        
    except KeyboardInterrupt:
        print("\nПрограмма прервана пользователем.")
    finally:
        monitor.running = False
        print("Завершение работы...")

if __name__ == "__main__":
    main()