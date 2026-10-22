import functions as fn
import voice_piper as vx   
import ears

VOICE_MODE = True                       # True = say "Hey Jarvis" / False = type in the terminal

if __name__ == "__main__":
    vx.load_in_background()             # Load Piper
    ears.load_in_background()           # Load the wake word and Whisper
    fn.check_and_start_ollama()         # Load Ollama
    print("=== Jarvis Initialized ===")
    if VOICE_MODE:
        print("Say 'Hey Jarvis' then your command. Say 'quit' or press Ctrl+C to close.\n")
    else:
        print("Type your message. Type 'quit' to close.\n")

    try:
        while True:
            if VOICE_MODE:
                vx.wait_until_done()    # Wait until Jarvis has finished speaking, so he does not hear himself
                print("[Ears] Waiting for 'Hey Jarvis'...")
                command = ears.listen()
            else:
                command = input("You : ").strip()

            if not command:
                continue

            if command.lower().strip(" .!?") in ["quit", "exit", "quitter"]:
                break

            fn.process_command(command)

    except KeyboardInterrupt:
        pass
    finally:
        fn.close_cleanly()