import clr
import os

hwtypes = ['Mainboard','SuperIO','CPU','RAM','GpuNvidia','GpuAti','TBalancer','Heatmaster','HDD']

def unblock_file(file_path):
    try:
        # Используем PowerShell для удаления метки Zone.Identifier
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
    for i in handle.Hardware:
        i.Update()
        for sensor in i.Sensors:
            parse_sensor(sensor)
        for j in i.SubHardware:
            j.Update()
            for subsensor in j.Sensors:
                parse_sensor(subsensor)

def parse_sensor(sensor):
    if sensor.Value and  str(sensor.SensorType) == 'Temperature':
        result = u'{} {} Temperature Sensor #{} {} - {}\u00B0C'\
                .format(hwtypes[sensor.Hardware.HardwareType], 
                        sensor.Hardware.Name, sensor.Index, 
                        sensor.Name, sensor.Value
                )
        print(result)

if __name__ == "__main__":
    HardwareHandle = initialize_openhardwaremonitor()
    fetch_stats(HardwareHandle)