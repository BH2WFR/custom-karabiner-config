import keyboard_events


def release_shift():
    keyboard_events.release_keys(keyboard_events.LEFT_SHIFT_KEY_CODE,
                                 keyboard_events.RIGHT_SHIFT_KEY_CODE)


if __name__ == "__main__":
    release_shift()
