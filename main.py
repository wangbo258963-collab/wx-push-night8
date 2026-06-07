import os
import random
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

import requests


WARM_WORDS = [
    "今天也辛苦啦，愿夜风替你吹走疲惫，愿梦里都是温柔。",
    "不管今天过得怎么样，你都已经很棒了，今晚就把自己交给好梦吧。",
    "愿你被生活温柔以待，也愿我这句晚安刚好落在你心上。",
    "忙碌的一天结束啦，记得放松肩膀，好好睡觉。",
    "今晚把烦恼暂时放一放，明天的阳光会重新抱抱你。",
]

ENCOURAGE_WORDS = [
    "明天也不用太着急，慢慢来，你想要的生活正在路上。",
    "你一直都很厉害，只是偶尔需要休息一下。",
    "愿你明天醒来，心里有光，脚下有路，眼前有期待。",
    "今天翻篇，明天继续闪闪发光。",
    "不用和别人比，你按自己的节奏往前走，就已经很好了。",
]

FUNNY_WORDS = [
    "今晚的任务：手机放下，被子盖好，脑袋清空，梦里暴富。",
    "检测到小可爱电量不足，请立刻连接被窝充电器。",
    "月亮已经上班了，你也该下班睡觉啦。",
    "晚安协议已生效：禁止胡思乱想，允许梦见快乐。",
    "请立刻进入睡眠模式，否则小被子将启动强制封印。",
]

POEMS = [
    "海上生明月，天涯共此时。",
    "晚来天欲雪，能饮一杯无。",
    "山中何事？松花酿酒，春水煎茶。",
    "星河秋一雁，砧杵夜千家。",
    "月上柳梢头，人约黄昏后。",
]

LOVE_WORDS = [
    "今天的晚风、月亮和星星，都替我说一句：我很想你。",
    "今晚不说大道理，只说我偏爱你。",
    "世界很大，但我的晚安只想发给你。",
    "如果梦有入口，希望今晚我能刚好遇见你。",
    "我把今天最后一点温柔，留给你这句晚安。",
]


class PushError(Exception):
    pass


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise PushError(f"缺少环境变量：{name}")
    return value


def load_config() -> Dict[str, Any]:
    users_raw = require_env("WECHAT_USER_OPENIDS")
    users = [item.strip() for item in users_raw.split(",") if item.strip()]

    if not users:
        raise PushError("WECHAT_USER_OPENIDS 为空，请填写接收人的 OpenID。")

    return {
        "app_id": require_env("WECHAT_APP_ID"),
        "app_secret": require_env("WECHAT_APP_SECRET"),
        "template_id": require_env("WECHAT_TEMPLATE_ID"),
        "weather_key": require_env("QWEATHER_KEY"),
        "region": os.getenv("REGION", "长沙市").strip() or "长沙市",
        "receiver_name": os.getenv("RECEIVER_NAME", "苏苏姐").strip() or "苏苏姐",
        "users": users,
    }


def request_json(
    url: str,
    params: Dict[str, Any] = None,
    method: str = "GET",
    body: Dict[str, Any] = None,
) -> Dict[str, Any]:
    try:
        if method == "POST":
            response = requests.post(url, params=params, json=body, timeout=20)
        else:
            response = requests.get(url, params=params, timeout=20)

        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        raise PushError(f"网络请求失败：{exc}")


def get_access_token(config: Dict[str, Any]) -> str:
    data = request_json(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={
            "grant_type": "client_credential",
            "appid": config["app_id"],
            "secret": config["app_secret"],
        },
    )

    if "access_token" not in data:
        raise PushError(f"获取 access_token 失败，请检查微信 appID 和 appSecret：{data}")

    return data["access_token"]


def get_location_id(config: Dict[str, Any]) -> Tuple[str, str]:
    data = request_json(
        "https://geoapi.qweather.com/v2/city/lookup",
        params={
            "location": config["region"],
            "key": config["weather_key"],
            "lang": "zh",
        },
    )

    if data.get("code") != "200" or not data.get("location"):
        raise PushError(f"城市查询失败，请检查 REGION 或 QWEATHER_KEY：{data}")

    location = data["location"][0]
    return location["id"], location.get("name", config["region"])


def get_weather_now(config: Dict[str, Any], location_id: str) -> Dict[str, Any]:
    data = request_json(
        "https://devapi.qweather.com/v7/weather/now",
        params={
            "location": location_id,
            "key": config["weather_key"],
            "lang": "zh",
            "unit": "m",
        },
    )

    if data.get("code") != "200" or "now" not in data:
        raise PushError(f"实时天气获取失败：{data}")

    return data["now"]


def get_weather_3d(config: Dict[str, Any], location_id: str) -> List[Dict[str, Any]]:
    data = request_json(
        "https://devapi.qweather.com/v7/weather/3d",
        params={
            "location": location_id,
            "key": config["weather_key"],
            "lang": "zh",
            "unit": "m",
        },
    )

    if data.get("code") != "200" or not data.get("daily"):
        raise PushError(f"天气预报获取失败：{data}")

    return data["daily"]


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        return default


def contains_any(text: str, words: List[str]) -> bool:
    return any(word in text for word in words)


def make_clothing_advice(
    now: Dict[str, Any],
    today: Dict[str, Any],
    tomorrow: Dict[str, Any],
) -> str:
    now_temp = to_int(now.get("temp"))
    min_temp = to_int(tomorrow.get("tempMin"), now_temp)
    max_temp = to_int(tomorrow.get("tempMax"), now_temp)
    uv_index = to_int(tomorrow.get("uvIndex"))
    precip = to_int(tomorrow.get("precip"))

    wind_scale = str(tomorrow.get("windScaleDay", ""))
    wind_dir = str(tomorrow.get("windDirDay", ""))

    weather_text = " ".join(
        [
            str(now.get("text", "")),
            str(today.get("textNight", "")),
            str(tomorrow.get("textDay", "")),
            str(tomorrow.get("textNight", "")),
        ]
    )

    advices = []

    if min_temp <= 0:
        advices.append("明天非常冷，羽绒服/厚棉服、毛衣或保暖内衣都安排上，围巾、手套、厚袜子也别忘。")
    elif min_temp <= 6:
        advices.append("明天很冷，建议穿羽绒服或厚外套，里面搭毛衣/卫衣；早晚尤其冷，别露脚踝。")
    elif min_temp <= 12:
        advices.append("明天偏冷，建议穿厚外套、卫衣或针织衫，早晚加一层更稳。")
    elif min_temp <= 18:
        advices.append("明天早晚有点凉，建议长袖加薄外套，中午热了可以脱。")
    elif max_temp <= 25:
        advices.append("明天气温比较舒服，长袖、薄外套或轻便春秋装都合适。")
    elif max_temp <= 31:
        advices.append("明天偏热，建议短袖、薄衬衫、透气裙装或轻薄裤装，尽量选舒服吸汗的。")
    elif max_temp <= 35:
        advices.append("明天很热，建议清凉透气的衣服，出门带水，尽量避开正午暴晒。")
    else:
        advices.append("明天高温明显，建议穿浅色、宽松、透气衣物，减少户外久站，记得补水防暑。")

    temp_diff = max_temp - min_temp

    if temp_diff >= 10:
        advices.append(
            f"昼夜温差约 {temp_diff}℃，建议洋葱式穿搭：里面轻薄，外面加外套，冷了能穿、热了能脱。"
        )

    if contains_any(weather_text, ["雷", "雷阵雨"]):
        advices.append(
            "有雷电相关天气，打雷害怕的话尽量早点回家，关好窗，别在树下、空旷处或水边停留；晚上可以开小夜灯，放点轻音乐，安心睡。"
        )

    if contains_any(weather_text, ["暴雨", "大雨", "中雨", "阵雨", "小雨", "雨"]):
        advices.append(
            "可能下雨，记得带伞；鞋子尽量穿防滑、不怕湿的，裤脚别太长，回家后及时擦干头发和脚。"
        )

    if precip >= 5:
        advices.append(f"预报降水量约 {precip}mm，雨感会比较明显，包里放纸巾，通勤路上慢一点。")

    if contains_any(weather_text, ["雪", "雨夹雪"]):
        advices.append("有降雪或雨夹雪可能，路面容易湿滑，鞋子选防滑的，出门慢慢走，保暖优先。")

    if max_temp >= 30:
        advices.append("夏天热的时候别硬扛，出门可以带遮阳伞/帽子，少喝冰太猛，容易肚子不舒服。")

    if max_temp >= 35:
        advices.append("高温天要特别注意防暑，水要小口多次喝，出现头晕、心慌、恶心就赶紧去阴凉处休息。")

    if min_temp <= 8:
        advices.append("冬天或冷空气天气，脖子、肚子、脚踝要护住，晚上睡觉盖好被子。")

    if any(ch in wind_scale for ch in ["4", "5", "6", "7", "8", "9"]):
        advices.append(f"明天{wind_dir}{wind_scale}级，风感会明显，外套最好选防风的。")

    if uv_index >= 7:
        advices.append(f"紫外线指数 {uv_index}，白天出门记得防晒，脸、脖子、手臂都照顾到。")
    elif uv_index >= 4:
        advices.append(f"紫外线指数 {uv_index}，白天出门简单防晒会更稳。")

    if min_temp <= 12 or temp_diff >= 8 or contains_any(weather_text, ["雨", "雪", "降温", "冷"]):
        advices.append(
            "感冒提醒：早晚别贪凉，淋雨后及时换干衣服；嗓子不舒服就少喝冰的，多喝温水，早点休息。"
        )

    return "\n".join(f"• {item}" for item in advices)


def build_message(config: Dict[str, Any]) -> Dict[str, str]:
    location_id, city_name = get_location_id(config)

    now = get_weather_now(config, location_id)
    daily = get_weather_3d(config, location_id)

    today = daily[0]
    tomorrow = daily[1] if len(daily) > 1 else daily[0]

    tonight_weather = (
        f"{city_name}今晚：{today.get('textNight')}，"
        f"最低约 {today.get('tempMin')}℃，"
        f"{today.get('windDirNight')} {today.get('windScaleNight')}级。"
    )

    tomorrow_weather = (
        f"明天：白天{tomorrow.get('textDay')}，夜间{tomorrow.get('textNight')}；"
        f"气温 {tomorrow.get('tempMin')}℃~{tomorrow.get('tempMax')}℃；"
        f"{tomorrow.get('windDirDay')} {tomorrow.get('windScaleDay')}级；"
        f"紫外线指数 {tomorrow.get('uvIndex')}。"
    )

    temperature = (
        f"当前：{now.get('text')}，{now.get('temp')}℃，"
        f"体感 {now.get('feelsLike')}℃，"
        f"{now.get('windDir')} {now.get('windScale')}级。"
    )

    return {
        "first": f"{config['receiver_name']}晚安( ˘ω˘ )",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "city": city_name,
        "tonight_weather": tonight_weather,
        "tomorrow_weather": tomorrow_weather,
        "temperature": temperature,
        "clothing_advice": make_clothing_advice(now, today, tomorrow),
        "warm_word": random.choice(WARM_WORDS),
        "encourage_word": random.choice(ENCOURAGE_WORDS),
        "funny_word": random.choice(FUNNY_WORDS),
        "poem": random.choice(POEMS),
        "love_word": random.choice(LOVE_WORDS),
        "remark": "盖好被子，别胡思乱想，早点睡觉，好梦呀 ❤️",
    }


def send_template_message(
    config: Dict[str, Any],
    access_token: str,
    to_user: str,
    message: Dict[str, str],
) -> None:
    data = {
        "touser": to_user,
        "template_id": config["template_id"],
        "url": "",
        "data": {
            key: {
                "value": value,
                "color": "#173177",
            }
            for key, value in message.items()
        },
    }

    result = request_json(
        "https://api.weixin.qq.com/cgi-bin/message/template/send",
        params={"access_token": access_token},
        method="POST",
        body=data,
    )

    if result.get("errcode") != 0:
        raise PushError(f"模板消息发送失败：{result}")

    print(f"发送成功：{mask_openid(to_user)}")


def mask_openid(openid: str) -> str:
    if len(openid) <= 8:
        return "***"
    return openid[:4] + "***" + openid[-4:]


def run_once() -> None:
    config = load_config()
    access_token = get_access_token(config)
    message = build_message(config)

    print("本次推送内容预览：")
    for key, value in message.items():
        print(f"[{key}] {value}")

    for user in config["users"]:
        send_template_message(config, access_token, user, message)

    print("全部推送完成。")


if __name__ == "__main__":
    try:
        run_once()
    except PushError as exc:
        print("运行失败：", exc)
        sys.exit(1)
    except Exception as exc:
        print("未知错误：", exc)
        sys.exit(1)
