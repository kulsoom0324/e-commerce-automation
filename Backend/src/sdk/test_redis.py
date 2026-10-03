import redis

r = redis.Redis(
    host="door-wheel-retrosteady-25658.db.redis.io",
    port=19507,
    username="default",
    password="l9EK4CPuWA0x4dSK80kEUcd7Zz6eLlQ",
    decode_responses=True
)

print(r.ping())