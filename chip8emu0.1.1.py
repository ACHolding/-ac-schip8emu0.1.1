import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import random

# Chip-8 CPU Emulator
class Chip8:
    def __init__(self):
        self.memory = bytearray(4096)
        self.V = bytearray(16)          # registers V0-VF
        self.I = 0                      # index register
        self.pc = 0x200                 # program counter starts at 0x200
        self.stack = []
        self.sp = 0
        self.delay_timer = 0
        self.sound_timer = 0
        self.display = bytearray(64 * 32)  # 64x32 pixels
        self.draw_flag = False
        self.key = bytearray(16)        # keypad state (0/1)
        self.waiting_for_key = False
        self.key_register = 0

        # fontset (0-9, A-F) loaded at 0x0
        fontset = [
            0xF0, 0x90, 0x90, 0x90, 0xF0, # 0
            0x20, 0x60, 0x20, 0x20, 0x70, # 1
            0xF0, 0x10, 0xF0, 0x80, 0xF0, # 2
            0xF0, 0x10, 0xF0, 0x10, 0xF0, # 3
            0x90, 0x90, 0xF0, 0x10, 0x10, # 4
            0xF0, 0x80, 0xF0, 0x10, 0xF0, # 5
            0xF0, 0x80, 0xF0, 0x90, 0xF0, # 6
            0xF0, 0x10, 0x20, 0x40, 0x40, # 7
            0xF0, 0x90, 0xF0, 0x90, 0xF0, # 8
            0xF0, 0x90, 0xF0, 0x10, 0xF0, # 9
            0xF0, 0x90, 0xF0, 0x90, 0x90, # A
            0xE0, 0x90, 0xE0, 0x90, 0xE0, # B
            0xF0, 0x80, 0x80, 0x80, 0xF0, # C
            0xE0, 0x90, 0x90, 0x90, 0xE0, # D
            0xF0, 0x80, 0xF0, 0x80, 0xF0, # E
            0xF0, 0x80, 0xF0, 0x80, 0x80  # F
        ]
        for i, byte in enumerate(fontset):
            self.memory[i] = byte

        self.reset()

    def reset(self):
        self.pc = 0x200
        self.I = 0
        self.sp = 0
        self.stack.clear()
        self.delay_timer = 0
        self.sound_timer = 0
        self.V = bytearray(16)
        self.display = bytearray(64 * 32)
        self.draw_flag = False
        self.waiting_for_key = False
        # clear memory except fontset
        self.memory[0x200:] = bytearray(4096 - 0x200)

    def load_rom(self, path):
        with open(path, 'rb') as f:
            data = f.read()
        if len(data) > 4096 - 0x200:
            raise ValueError("ROM too large")
        self.reset()
        self.memory[0x200:0x200+len(data)] = data

    def cycle(self):
        if self.waiting_for_key:
            return  # pause CPU until key press
        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc+1]
        self.execute(opcode)
        if not self.waiting_for_key:
            self.pc += 2

    def execute(self, opcode):
        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4
        nnn = opcode & 0x0FFF
        kk = opcode & 0x00FF
        n = opcode & 0x000F

        if opcode == 0x00E0:  # CLS
            self.display = bytearray(64 * 32)
            self.draw_flag = True
        elif opcode == 0x00EE:  # RET
            self.sp -= 1
            self.pc = self.stack[self.sp]
        elif opcode & 0xF000 == 0x1000:  # JP addr
            self.pc = nnn - 2  # pc will be incremented by 2 after cycle
        elif opcode & 0xF000 == 0x2000:  # CALL addr
            self.stack.append(self.pc)
            self.sp += 1
            self.pc = nnn - 2
        elif opcode & 0xF000 == 0x3000:  # SE Vx, byte
            if self.V[x] == kk:
                self.pc += 2
        elif opcode & 0xF000 == 0x4000:  # SNE Vx, byte
            if self.V[x] != kk:
                self.pc += 2
        elif opcode & 0xF000 == 0x5000:  # SE Vx, Vy
            if self.V[x] == self.V[y]:
                self.pc += 2
        elif opcode & 0xF000 == 0x6000:  # LD Vx, byte
            self.V[x] = kk
        elif opcode & 0xF000 == 0x7000:  # ADD Vx, byte
            self.V[x] = (self.V[x] + kk) & 0xFF
        elif opcode & 0xF00F == 0x8000:  # LD Vx, Vy
            self.V[x] = self.V[y]
        elif opcode & 0xF00F == 0x8001:  # OR Vx, Vy
            self.V[x] |= self.V[y]
        elif opcode & 0xF00F == 0x8002:  # AND Vx, Vy
            self.V[x] &= self.V[y]
        elif opcode & 0xF00F == 0x8003:  # XOR Vx, Vy
            self.V[x] ^= self.V[y]
        elif opcode & 0xF00F == 0x8004:  # ADD Vx, Vy
            result = self.V[x] + self.V[y]
            self.V[0xF] = 1 if result > 255 else 0
            self.V[x] = result & 0xFF
        elif opcode & 0xF00F == 0x8005:  # SUB Vx, Vy
            self.V[0xF] = 1 if self.V[x] > self.V[y] else 0
            self.V[x] = (self.V[x] - self.V[y]) & 0xFF
        elif opcode & 0xF00F == 0x8006:  # SHR Vx {, Vy}
            self.V[0xF] = self.V[x] & 0x1
            self.V[x] >>= 1
        elif opcode & 0xF00F == 0x8007:  # SUBN Vx, Vy
            self.V[0xF] = 1 if self.V[y] > self.V[x] else 0
            self.V[x] = (self.V[y] - self.V[x]) & 0xFF
        elif opcode & 0xF00F == 0x800E:  # SHL Vx {, Vy}
            self.V[0xF] = (self.V[x] >> 7) & 0x1
            self.V[x] = (self.V[x] << 1) & 0xFF
        elif opcode & 0xF00F == 0x9000:  # SNE Vx, Vy
            if self.V[x] != self.V[y]:
                self.pc += 2
        elif opcode & 0xF000 == 0xA000:  # LD I, addr
            self.I = nnn
        elif opcode & 0xF000 == 0xB000:  # JP V0, addr
            self.pc = (self.V[0] + nnn) - 2
        elif opcode & 0xF000 == 0xC000:  # RND Vx, byte
            self.V[x] = random.randint(0, 255) & kk
        elif opcode & 0xF000 == 0xD000:  # DRW Vx, Vy, nibble
            xpos = self.V[x] & 63
            ypos = self.V[y] & 31
            self.V[0xF] = 0
            for row in range(n):
                sprite_byte = self.memory[self.I + row]
                for col in range(8):
                    if (sprite_byte & (0x80 >> col)) != 0:
                        px = (xpos + col) & 63
                        py = (ypos + row) & 31
                        idx = py * 64 + px
                        if self.display[idx] == 1:
                            self.V[0xF] = 1
                        self.display[idx] ^= 1
            self.draw_flag = True
        elif opcode & 0xF0FF == 0xE09E:  # SKP Vx
            if self.key[self.V[x] & 0xF] != 0:
                self.pc += 2
        elif opcode & 0xF0FF == 0xE0A1:  # SKNP Vx
            if self.key[self.V[x] & 0xF] == 0:
                self.pc += 2
        elif opcode & 0xF0FF == 0xF007:  # LD Vx, DT
            self.V[x] = self.delay_timer
        elif opcode & 0xF0FF == 0xF00A:  # LD Vx, K (wait)
            self.waiting_for_key = True
            self.key_register = x
        elif opcode & 0xF0FF == 0xF015:  # LD DT, Vx
            self.delay_timer = self.V[x]
        elif opcode & 0xF0FF == 0xF018:  # LD ST, Vx
            self.sound_timer = self.V[x]
        elif opcode & 0xF0FF == 0xF01E:  # ADD I, Vx
            self.I = (self.I + self.V[x]) & 0xFFFF
        elif opcode & 0xF0FF == 0xF029:  # LD F, Vx (font)
            self.I = self.V[x] * 5
        elif opcode & 0xF0FF == 0xF033:  # LD B, Vx
            val = self.V[x]
            self.memory[self.I] = val // 100
            self.memory[self.I+1] = (val // 10) % 10
            self.memory[self.I+2] = val % 10
        elif opcode & 0xF0FF == 0xF055:  # LD [I], Vx
            for i in range(x+1):
                self.memory[self.I + i] = self.V[i]
        elif opcode & 0xF0FF == 0xF065:  # LD Vx, [I]
            for i in range(x+1):
                self.V[i] = self.memory[self.I + i]
        else:
            print(f"Unknown opcode: {opcode:04X}")

    def key_down(self, key_index):
        self.key[key_index] = 1
        if self.waiting_for_key:
            self.V[self.key_register] = key_index
            self.waiting_for_key = False

    def key_up(self, key_index):
        self.key[key_index] = 0

    def update_timers(self):
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1


# GUI Application
class Chip8EmulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ac's chip 8 emulator 0.1")
        self.root.configure(bg="#1e1e3c")  # dark blue hue
        self.root.resizable(False, False)

        self.cpu = Chip8()
        self.running = False
        self.rom_loaded = False
        self.emu_thread = None
        self.step_lock = threading.Lock()
        self.cycle_rate = 700  # Hz approximate

        # key mapping: QWERTY layout -> Chip-8 keypad
        self.key_map = {
            '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
            'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
            'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
            'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF
        }

        self.setup_menu()
        self.setup_ui()

        # display bitmap
        self.scale = 10
        self.display_w = 64 * self.scale
        self.display_h = 32 * self.scale
        self.canvas.config(width=self.display_w, height=self.display_h)
        self.refresh_display()

        # bind keys
        self.root.bind('<KeyPress>', self.on_key_down)
        self.root.bind('<KeyRelease>', self.on_key_up)

        # timer update
        self.update_timer()

    def setup_menu(self):
        menubar = tk.Menu(self.root, bg="#1e1e3c", fg="#4a90e2", activebackground="#4a90e2", activeforeground="white")
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0, bg="#1e1e3c", fg="#4a90e2", activebackground="#4a90e2", activeforeground="white")
        file_menu.add_command(label="Load ROM", command=self.load_rom)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        control_menu = tk.Menu(menubar, tearoff=0, bg="#1e1e3c", fg="#4a90e2", activebackground="#4a90e2", activeforeground="white")
        control_menu.add_command(label="Run", command=self.run_emulation)
        control_menu.add_command(label="Pause", command=self.pause_emulation)
        control_menu.add_command(label="Step", command=self.step_emulation)
        control_menu.add_command(label="Reset", command=self.reset_emulation)
        menubar.add_cascade(label="Control", menu=control_menu)

    def setup_ui(self):
        # main frame
        main_frame = tk.Frame(self.root, bg="#1e1e3c")
        main_frame.pack(padx=10, pady=10)

        # canvas for display
        self.canvas = tk.Canvas(main_frame, bg="black", highlightthickness=0)
        self.canvas.pack()

        # button frame
        btn_frame = tk.Frame(main_frame, bg="#1e1e3c")
        btn_frame.pack(pady=10)

        # buttons with black background, blue text
        btn_style = {"bg": "black", "fg": "#4a90e2", "activebackground": "#2a2a5a", "activeforeground": "white",
                     "relief": "raised", "bd": 2, "font": ("Consolas", 10), "width": 8}

        tk.Button(btn_frame, text="Load ROM", command=self.load_rom, **btn_style).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Run", command=self.run_emulation, **btn_style).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Pause", command=self.pause_emulation, **btn_style).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Step", command=self.step_emulation, **btn_style).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Reset", command=self.reset_emulation, **btn_style).pack(side=tk.LEFT, padx=5)

        # status label (blue text)
        self.status_label = tk.Label(main_frame, text="Ready", fg="#4a90e2", bg="#1e1e3c", font=("Consolas", 10))
        self.status_label.pack()

    def refresh_display(self):
        self.canvas.delete("all")
        for y in range(32):
            for x in range(64):
                if self.cpu.display[y * 64 + x]:
                    x1 = x * self.scale
                    y1 = y * self.scale
                    x2 = x1 + self.scale
                    y2 = y1 + self.scale
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="#4a90e2", outline="")  # blue pixel

    def load_rom(self):
        path = filedialog.askopenfilename(filetypes=[("Chip-8 ROMs", "*.ch8 *.rom *.bin"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.cpu.load_rom(path)
            self.rom_loaded = True
            self.status_label.config(text=f"Loaded: {path.split('/')[-1]}")
            self.refresh_display()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ROM: {e}")

    def run_emulation(self):
        if not self.rom_loaded:
            messagebox.showwarning("No ROM", "Load a ROM first.")
            return
        if not self.running:
            self.running = True
            self.emu_thread = threading.Thread(target=self.emulation_loop, daemon=True)
            self.emu_thread.start()
            self.status_label.config(text="Running...")

    def pause_emulation(self):
        self.running = False
        self.status_label.config(text="Paused")

    def step_emulation(self):
        if not self.rom_loaded:
            messagebox.showwarning("No ROM", "Load a ROM first.")
            return
        if self.running:
            self.running = False  # stop auto run
        self.cpu.cycle()
        self.refresh_display()
        self.status_label.config(text=f"PC: {self.cpu.pc:04X}")

    def reset_emulation(self):
        self.running = False
        if self.rom_loaded:
            self.cpu.reset()
            self.refresh_display()
            self.status_label.config(text="Reset")

    def emulation_loop(self):
        while self.running:
            start = time.perf_counter()
            for _ in range(8):  # execute multiple cycles per frame
                self.cpu.cycle()
            self.cpu.update_timers()
            self.root.after(0, self.refresh_display)
            # maintain rough cycle rate
            elapsed = time.perf_counter() - start
            target = 1 / (self.cycle_rate / 8)
            if elapsed < target:
                time.sleep(target - elapsed)

    def update_timer(self):
        if self.running:
            # timers handled in loop, but also ensure they tick at ~60Hz
            pass
        self.root.after(16, self.update_timer)

    def on_key_down(self, event):
        key = event.keysym.lower()
        if key in self.key_map:
            self.cpu.key_down(self.key_map[key])

    def on_key_up(self, event):
        key = event.keysym.lower()
        if key in self.key_map:
            self.cpu.key_up(self.key_map[key])

def main():
    root = tk.Tk()
    app = Chip8EmulatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
