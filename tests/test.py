# Đây là file để test Lumos Editor
import random

n = random.randint(1, 100)
while True:
    g = int(input("Game đoán số (1 -> 100): "))
    if g == n:
        print("Đúng rồi.")
        break
    if g < n:
        print("Số bí mật lớn hơn.")
    else:
        print("Số bí mật nhỏ hơn.")
