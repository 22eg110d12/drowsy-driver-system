import pygame

pygame.mixer.init()

try:
    sound = pygame.mixer.Sound("alert.wav")
    sound.play()
    input("Press Enter to exit after sound plays...")
except Exception as e:
    print(f"[ERROR] Could not play sound: {e}")