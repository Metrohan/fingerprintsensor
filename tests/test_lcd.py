from ili9486 import ILI9486

tft = ILI9486()

# Ekranı siyah yap
tft.fill_screen(0, 0, 0)

# Sol yarı yeşil, sağ yarı mavi
tft.fill_rect(0, 0, 240, 320, 0, 150, 0)
tft.fill_rect(240, 0, 240, 320, 0, 0, 180)

print("Bitti.")