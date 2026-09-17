from tools.weather_tool import WeatherQueryTool

for city in ["北京", "武汉", "上海", "广州"]:
    print(WeatherQueryTool().run(city))
    print("---")