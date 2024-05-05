"""
Main code

"""

import time


def run_timer() -> None:
    print(
        "Press Enter to start working and to pause/resume. "
        "Type 'exit' and press Enter to quit."
    )

    total_time: float = 0.0
    working: bool = False
    start_time: float = 0.0

    while True:
        try:
            user_input: str = input()
            if user_input.lower() == 'exit':
                if working:
                    total_time += time.time() - start_time
                break
        except EOFError:
            print("\nCtrl-D detected, exiting...")
            if working:
                total_time += time.time() - start_time
            break

        if working:
            total_time += time.time() - start_time
            working = False
            print("Work paused. Press Enter to resume.")
        else:
            start_time = time.time()
            working = True
            print("Working... Press Enter to pause.")

    hours, remainder = divmod(total_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(
        f"Total work time in this session: "
        f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    )
