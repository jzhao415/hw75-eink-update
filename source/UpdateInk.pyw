from datetime import datetime
import time
import configparser
import os
import requests
import pytz
import random
# import inquirer
import zmkx
import sched
from psutil import *
from PIL import Image, ImageDraw, ImageFont
import xml.etree.ElementTree as ET

# 静态的路径名、图片与其它变量预先加载，避免反复读盘。
font12 = ImageFont.truetype('img/fusion-pixel-12px-monospaced-zh_hans.ttf', 12)
font16 = ImageFont.truetype('img/fusion-pixel-10px-monospaced-zh_hans.ttf', 16)
font20 = ImageFont.truetype('img/fusion-pixel-10px-monospaced-zh_hans.ttf', 20)
# font24 = ImageFont.truetype('img/fusion-pixel-12px-monospaced-zh_hans.ttf', 24)
font48 = ImageFont.truetype('img/fusion-pixel-10px-monospaced-zh_hans.ttf', 48)
# font60 = ImageFont.truetype('img/fusion-pixel-10px-monospaced-zh_hans.ttf', 60)

font12b = ImageFont.truetype('img/LiberationMono-Bold.ttf', 12)
font16b = ImageFont.truetype('img/LiberationMono-Bold.ttf', 16)
font20b = ImageFont.truetype('img/LiberationMono-Bold.ttf', 20)

cpu_path = "./img/cpu.png"
mem_path = "./img/men.png"
image_path = "./img/"
line_path = "./img/line.png"
weather_icon_path = "./icon/"
nowtemp_path = "./img/nowtemp.png"
wave_path = "./img/wave.png"
cpu_icon = Image.open(cpu_path)
mem_icon = Image.open(mem_path)
metar_bg_path = "./img/metar_bg.png"
scheduler = sched.scheduler(time.time, time.sleep)


def font(actual_size: int = 10, display_size: int = 10):
    """
    方便灵活定义字体大小，暂不启用
    """
    if actual_size not in (10, 12):
        print("Invalid actual size, currently support 10 or 12")
        return
    ttf: str = 'img/fusion-pixel-'+str(actual_size)+'px-monospaced-zh_hans.ttf'
    return ImageFont.truetype(ttf, display_size)


def get_device(features=[]):
    """
    调用ZMKX包来获取设备实例。
    """
    devices = zmkx.find_devices(features=features)
    if len(devices) == 0:
        print('未找到符合条件的设备')
        return None
    if len(devices) == 1:
        return devices[0]
    # choice = inquirer.prompt([
    #     inquirer.List('device', message='有多个设备，请选择', choices=[
    #         (f'{d.manufacturer} {d.product} (SN: {d.serial})', d)
    #         for d in devices
    #     ]),
    # ])
    # if choice is None:
    #     return None
    # return choice['device']


# 实例化墨水屏设备，作为全局变量，避免频繁调用get_device方法。
eink_device = get_device(features=['eink'])


def draw_text_on_canvas(text: str, canvas: Image, font=None, x_offset=0, y_offset=0, center=True, screen_width=128, fill=0X00, img_draw: ImageDraw = None, **kwargs) -> Image:
    if img_draw == None:
        img_draw = ImageDraw.Draw(canvas)
    if font == None:
        print("请指定字体")
        return
    text_width = img_draw.textlength(text, font=font)
    # if text_width>screen_width:
    #     print("内容过长")
    #     return
    x = x_offset+int((screen_width-text_width)/2) if center else x_offset
    img_draw.text((x, y_offset),
                  text, font=font, fill=fill, align='center', **kwargs)
    return canvas

def get_metar_xml() -> dict:
    """
    Parse METAR XML response and return a dictionary with station_id as the key and other fields as values.

    Args:
        xml_string (str): The XML response as a string.

    Returns:
        dict: A dictionary with station_id as the key and a dictionary of other fields as values.
    """
    config = configparser.ConfigParser()
    config_file = os.path.join(os.getcwd(), 'config.ini')
    config.read(config_file)
    airports = config.get('DEFAULT', 'airports')

    params = {
        'ids': airports,
        'format': 'xml',
        'taf': 'false',
        'hours': 2,
    }
    session = requests.Session()
    aviation_weather_base_url = "https://aviationweather.gov/api/data/metar"

    session = requests.Session()
    response = session.get(aviation_weather_base_url, params=params)
    response.raise_for_status()

    # Initialize dictionary
    result = parse_metar_response(response.text)

    return result

def parse_metar_response(xml_string):
    """
    Parse METAR XML response and return a dictionary with station_id as the key and other fields as values.

    Args:
        xml_string (str): The XML response as a string.

    Returns:
        dict: A dictionary with station_id as the key and a dictionary of other fields as values.
    """
    # Parse the XML
    root = ET.fromstring(xml_string)

    # Initialize dictionary
    result = {}

    # Iterate through all METAR elements
    for metar_element in root.findall(".//METAR"):
        # Extract key (station_id)
        station_id = metar_element.findtext("station_id")
        obs_time = metar_element.findtext("observation_time")
        obs_time_str = None
        if obs_time:
            dt = datetime.fromisoformat(obs_time.replace("Z", "+00:00"))
            obs_time_str = dt.strftime("%d%H%MZ")
        # Convert dew point temperature to int to save screen space
        dewp = metar_element.findtext("dewpoint_c")
        dewp_str = ""
        if dewp is not None:
            dewp_str = f"{int(float(dewp))}"

        temp = metar_element.findtext("temp_c")
        temp_str = ""
        if temp is not None:
            temp_str = f"{int(float(temp))}"

        wdir = metar_element.findtext("wind_dir_degrees")
        wspd = metar_element.findtext("wind_speed_kt")
        wgst = metar_element.findtext("wind_gust_kt")
        wind_info = f"{wdir}/{wspd}" if wdir is not None and wspd is not None else None
        if wind_info is not None:
            if wgst is not None:
                wind_info += f"G{wgst}kts"
            else:
                wind_info += "kts"

        sky_conditions = []
        for condition in metar_element.findall("sky_condition"):
            sky_cover = condition.get("sky_cover")
            cloud_base = condition.get("cloud_base_ft_agl")
            if cloud_base:
                sky_conditions.append(f"{sky_cover}{cloud_base}")
            else:
                sky_conditions.append(sky_cover)
        clouds =  " ".join(sky_conditions)
        # Extract relevant fields
        metar_data = {
            "raw_text": metar_element.findtext("raw_text"),
            "observation_time": obs_time_str,
            "temp_c": temp_str,
            "dewpoint_c": dewp_str,
            "wind": wind_info,
            "visibility_statute_mi": metar_element.findtext("visibility_statute_mi") + "ms",
            "altim_in_hg": metar_element.findtext("altim_in_hg"),
            "sea_level_pressure_mb": metar_element.findtext("sea_level_pressure_mb"),
            "auto_station": metar_element.find("quality_control_flags/auto_station").text == "TRUE",
            "flight_category": metar_element.findtext("flight_category"),
            "metar_type": metar_element.findtext("metar_type"),
            "elevation_m": metar_element.findtext("elevation_m"),
            "cloud": clouds
        }

        # Assign to result
        if station_id:
            result[station_id] = metar_data
    print(f"xml metar data: {result}")
    return result

def get_weather_info() -> dict:
    """
    use api.weather.gov 
    use point API to get caw and gridXY from lat/long https://api.weather.gov/points/39.2767,-76.8994
    then use forecast api to get detailed forecast weather
    请注意：
    1.接口每日的请求次数有限，避免频繁调用此方法。氪金用户当我没说。
    2. config.ini的具体配置方法参见hellSakura大佬的教程。
    3. 简略了检验返回结果的逻辑，如果天气信息不正常，请优先调试本方法。
    Returns: 
    dict: 包含天气信息的字典。
    """
    config = configparser.ConfigParser()
    config_file = os.path.join(os.getcwd(), 'config.ini')
    config.read(config_file)
    key = config.get('DEFAULT', 'key')
    city = config.get('DEFAULT', 'city_id')

    params = {
        'appid': key,
        'id' : city,
        'units' : 'imperial'
    }
    session = requests.Session()
    current_weather_url = "https://api.openweathermap.org/data/2.5/weather"

    with session.get(current_weather_url, params=params) as r:
        r.raise_for_status()

        try:
            main_data = r.json()['weather']
            temp_data = r.json()['main']
            wind_data = r.json()['wind']
            if 'deg' in wind_data:
                wind_data['dir'] = degree_to_direction(wind_data['deg'])

        except KeyError:
            raise ValueError(r.text)
        weather_info = {
            'desc': main_data[0]['main'],
            'icon': main_data[0]['icon'],
            'temp': temp_data['temp'],
            'temp_min': temp_data['temp_min'],
            'temp_max': temp_data['temp_max'],
        }
        if 'speed' in wind_data and 'dir' in wind_data:
            weather_info['wind'] = f"{wind_data['dir']}@{wind_data['speed']:.1f}"
        print("weather info: ", weather_info)
        return weather_info

def degree_to_direction(degree):
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = round(degree / 45)
    return directions[idx % 8]

def get_cpu_and_mem_info() -> dict:
    """
    利用psutil包实现读取CPU和内存的使用状况

    Returns:
        dict: 包含CPU频率、CPU使用率、内存总量、内存可用量的字典。
    """
    cpu = str(cpu_percent(0.5))+'%'
    cpu_frequency = cpu_freq().current
    cpu_frequency_ghz = round(cpu_frequency / 1000, 1)
    mem = virtual_memory()
    mem_total= round((float(mem.total) / 1024 / 1024 / 1024),1)
    mem_avail = round((float(mem.available) / 1024 / 1024 / 1024),1)
    h={
        'cpu_frequency':cpu_frequency_ghz,
        'cpu_percentage':cpu,
        'mem_total':mem_total,
        'mem_avail':mem_avail
    }
    return h


def update_eink(canvas: Image, x=0, y=0, width=-1, height=-1, partial=True):
    """
    更新屏幕的方法，调用了ZMKX提供的API，非常方便。
    请注意：
    1. 图片(即canvas)的长宽在加上对应的偏移量后不得超出屏幕界限，否则报错。
    2. 图片的宽度(width)必须为8的整数倍，原理上来讲，len(canvas.tobytes())/width/height*8 计算后必须为1。

    Args:
    x (int): 图片在屏幕上的x坐标，默认为0
    y (int): 图片在屏幕上的y坐标，默认为0
    width (int): 图片的宽度，默认自动计算，不建议调整。
    height (int): 图片的高度，默认自动计算，不建议调整。
    partial (bool): 是否进行局部刷新，默认局刷。
    """
    width = width if width > 0 else canvas.width
    height = height if height > 0 else canvas.height
    # print("width",width,"height",height)
    if eink_device == None :
        return 
    device = eink_device
    try:
        with device.open() as device:
            device.eink_set_image(canvas.tobytes(), x=x, y=y,
                              width=width, height=height, partial=partial)
    except Exception as err:
        print("fail to update eink due to", err)
        device = get_device(features=['eink'])
        if device != None:
            globals()["eink_device"] = device
            print("successfully rediscovered device")


def draw_hw_canvas(x_offset=16, y_offset=0, refresh_interval=10) -> None:
    """
    更新屏幕上的硬件信息，只更新数值部分，不更新小Logo。
    默认出现在屏幕顶部，可通过指定x_offset与y_offset来调整渲染位置。
    默认每10秒刷新一次。
    """
    canvas = Image.new('1', (128-16, 50), color=0xff)
    img_draw = ImageDraw.Draw(canvas)
    h_info = get_cpu_and_mem_info()
    print("更新硬件信息：",h_info)
    cpu_frequency = str(h_info['cpu_frequency'])
    if len(cpu_frequency) < 5:
        cpu_frequency = ' '+cpu_frequency
    cpu_percentage = str(h_info['cpu_percentage'])
    if len(cpu_percentage) < 5:
        cpu_percentage = ' '+cpu_percentage
    mem_total = h_info['mem_total']
    mem_avail = h_info['mem_avail']
    mem_total = h_info['mem_total']
    mem_avail = h_info['mem_avail']
    mem_used = str(round((1-mem_avail/mem_total)*100, 1))+"%"
    if len(mem_used) < 5:
        mem_used = ' '+mem_used
    if len(str(mem_avail)) < 4:
        mem_avail = ' '+str(mem_avail)

    line1 = "Used:"+str(cpu_percentage)
    img_draw.text((0, 0), line1, font=font12, fill=0x00, align='center')

    line2 = "Freq:"+str(cpu_frequency)+"G"
    img_draw.text((0, 12), line2, font=font12, fill=0x00, align='center')

    line3 = "Used:"+mem_used
    img_draw.text((0, 26), line3, font=font12, fill=0x00, align='center')

    line4 = "Free:" + str(mem_avail) + "G"
    img_draw.text((0, 38), line4, font=font12, fill=0x00, align='center')

    update_eink(canvas, x=x_offset, y=y_offset,partial=True)
    scheduler.enter(refresh_interval, 1, draw_hw_canvas)

def draw_weather_canvas(x_offset=0, y_offset=186, refresh_interval=30*60) -> None:
    """
    查询天气数据并渲染。
    默认出现在屏幕底部，可通过指定x_offset与y_offset来调整渲染位置。
    每半小时查询并更新一次天气情况。因为是刷新间隔最长的方法，默认使用全局刷新来清理屏幕。
    """
    print("更新天气数据……")
    canvas = Image.new('1', (128, 100), 0xFF)
    w_info = get_weather_info()

    current_desc = w_info['desc']
    icon = w_info['icon']
    tempnow = w_info['temp']
    temp_min = w_info['temp_min']
    temp_max = w_info['temp_max']
    wind = w_info['wind']
    
    # 将温度值转换为带有符号的字符串
    tempnow_str = "{:d}".format(int(tempnow))
    temp_min_str = "{:d}".format(int(temp_min))
    temp_max_str = "{:d}".format(int(temp_max))
    # 计算温度值字符串的长度
    tempnow_str_len = len(tempnow_str)
    temp_min_str_len = len(temp_min_str)
    temp_max_str_len = len(temp_max_str)
    # 计算温度值字符串在新图片上的水平偏移量

    temp_min_offset_x = (64 - (12 * temp_min_str_len + 8)) // 2
    tempnow_offset_x = (128 - (12 * tempnow_str_len + 8)) // 2 + 40
    temp_max_offset_x = 64 + (64 - (12 * temp_max_str_len + 8))

    # draw weather icon
    weather_image = Image.open(weather_icon_path + icon + ".png")
    canvas.paste(weather_image, (6, 0))

    # 将温度值字符串中的每个字符分别加载对应的图片，并粘贴到新图片上
    tempmin_y_offset = 65
    for min, ch in enumerate(temp_min_str):
        if ch == "-":
            # 加载减号图片
            minus_image = Image.open(image_path + "minus.png")
            canvas.paste(minus_image, (temp_min_offset_x, tempmin_y_offset))
        else:
            # 加载对应数字图片
            digit_image = Image.open(image_path + ch + ".png")
            canvas.paste(digit_image, (temp_min_offset_x +
                         min * 12, tempmin_y_offset))

    tempmax_y_offset = 65
    for max, ch in enumerate(temp_max_str):
        if ch == "-":
            minus_image = Image.open(image_path + "minus.png")
            canvas.paste(minus_image, (temp_max_offset_x, tempmax_y_offset))
        else:
            digit_image = Image.open(image_path + ch + ".png")
            canvas.paste(digit_image, (temp_max_offset_x +
                         max * 12, tempmax_y_offset))

    tempnow_y_offset = 83
    for now, ch in enumerate(tempnow_str):
        if ch == "-":
            minus_image = Image.open(image_path + "minus.png")
            canvas.paste(minus_image, (tempnow_offset_x, tempnow_y_offset))
        else:
            digit_image = Image.open(image_path + ch + ".png")
            canvas.paste(digit_image, (tempnow_offset_x +
                         now * 12, tempnow_y_offset))

    # 将中文图片粘贴到新图片上
    draw_text_on_canvas(current_desc, canvas, font20, center=False, x_offset=65, y_offset=35)
    draw_text_on_canvas(wind, canvas, font20, center=False, x_offset=65, y_offset=15)

    # 将温度单位图片粘贴到新图片上
    temp_unit_image = Image.open(image_path + "temp_unit.png")
    canvas.paste(temp_unit_image, (tempnow_offset_x +
                 now * 12 + 12, tempnow_y_offset))

    # 将其他图片粘贴到新图片上
    nowtemp_image = Image.open(nowtemp_path)
    canvas.paste(nowtemp_image, (8, 80))
    wave_image = Image.open(wave_path)
    canvas.paste(wave_image, (58, 69))
    
    update_eink(canvas, x=x_offset, y=y_offset, partial=False)

    scheduler.enter(refresh_interval, 1, draw_weather_canvas)

def draw_hw_icons(x_offset=0, y_offset=0):
    """
    加载CPU与内存图标，默认出现在屏幕左上角
    """
    # 垂直间距
    v_gap = 5
    canvas = Image.new('1', (16, 50), color=0xFF)
    canvas.paste(cpu_icon, (0, 4))
    canvas.paste(mem_icon, (0, v_gap+26))
    update_eink(canvas, x=x_offset, y=y_offset, partial=True)

def format_temp(value):
                    if value is not None and abs(value) < 10 and value != 0:
                        return f"{value:.1f}"
                    return f"{int(value)}" if value is not None else None

def draw_metar_canvas(x_offset=0, y_offset=0):
    """
    Display the METAR information background
    """
    canvas = Image.new('1', (128, 128))
    metar_bg = Image.open(metar_bg_path)
    canvas.paste(metar_bg, (0, 4))
    img_draw = ImageDraw.Draw(canvas)
    metar_info = get_metar_xml()

    icao = random.choice(list(metar_info.keys()))
    metar = metar_info[icao]
    obs_time = metar['observation_time']
    wind = metar['wind']
    temp = metar['temp_c']
    dewp = metar['dewpoint_c']
    altim = metar['altim_in_hg']
    visib = metar['visibility_statute_mi']
    category = metar['flight_category']
    cloud = metar['cloud']
    img_draw.text((4,7), icao, font=font16b, fill=0x00, align='center') 
    img_draw.text((72,10), obs_time, font=font12b, fill=0x00, align='center') 
    img_draw.text((23,33), wind, font=font16b, fill=0x00, align='center')
    img_draw.text((16, 60), temp, font=font12b, fill=0x00, align='center')
    img_draw.text((55, 60), dewp, font=font12b, fill=0x00, align='center')
    img_draw.text((95, 60), altim, font=font12b, fill=0x00, align='center')
    img_draw.text((25, 86), visib, font=font12b, fill=0x00, align='center')
    img_draw.text((85, 82), category, font=font16b, fill=0x00, align='center')
    img_draw.text((22, 110), cloud, font=font12b, fill=0x00, align='center')

    update_eink(canvas, x=x_offset, y=y_offset, partial=True)
    scheduler.enter(60*5, 1, draw_metar_canvas)

def draw_clock_canvas(x_offset=0, y_offset=80):
    """
    更新时钟信息。
    默认出现在屏幕中间，可通过指定x_offset与y_offset来调整渲染位置。
    因为精度为分钟，故每分钟更新一次。
    """
    print("更新时钟数据")
    canvas = Image.new('1', (128, 50), color=0xff)
    img_draw = ImageDraw.Draw(canvas)
    now = time.localtime()
    hour = time.strftime("%H", now)
    minute = time.strftime("%M", now)
    print(now)
    
    draw_text_on_canvas(hour+':'+minute, canvas,
                        font=font48, x_offset=2, stroke_width=1)
    update_eink(canvas, x=x_offset, y=y_offset, partial=False)
    scheduler.enter(60, 1, draw_clock_canvas)


def draw_calendar_canvas(x_offset=0, y_offset=180):
    canvas = Image.new('1', (128, 50), color=0xff)
    img_draw = ImageDraw.Draw(canvas)
    now = time.localtime()
    weekdays = {
        0: "MONDAY",
        1: "TUESDAY",
        2: "WEDNESDAY",
        3: "THURSDAY",
        4: "FRIDAY",
        5: "SATURDAY",
        6: "SUNDAY"
    }
    month, day, week = now.tm_mon, now.tm_mday, weekdays[now.tm_wday]
    date = str(month)+"月"+str(day)+"日"
    draw_text_on_canvas(date, canvas, font20, img_draw=img_draw)
    draw_text_on_canvas(week, canvas, font20, y_offset=26, img_draw=img_draw)
    update_eink(canvas, x=x_offset, y=y_offset, partial=True)


def clean_screen(x=128, y=296, x_offset=0, y_offset=0):
    print("初始化屏幕……")
    all_white = Image.new("1", (x, y), color=0xFF)
    all_black = Image.new("1", (x, y), color=0x00)
    update_eink(all_black, x=x_offset, y=y_offset)
    time.sleep(0.1)
    update_eink(all_white, x=x_offset, y=y_offset)
    time.sleep(0.1)
    update_eink(all_black, x=x_offset, y=y_offset, partial=False)
    time.sleep(0.1)
    update_eink(all_white, x=x_offset, y=y_offset, partial=False)


if __name__ == '__main__':
    clean_screen()
    draw_metar_canvas()
    draw_calendar_canvas(0,130)
    draw_weather_canvas(0,185)
    # draw_clock_canvas(0,80)
    # draw_hw_canvas()
    scheduler.run()
