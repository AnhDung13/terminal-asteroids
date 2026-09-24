# Terminal Space War

Game bắn phi thuyền chạy ngay trong terminal, viết bằng Python thuần, không cần
cài thêm gì. Bạn lái một phi thuyền chống lại cả một hạm đội, cứ năm wave có
một boss nhỏ, mười wave có một boss lớn, và sau mỗi boss lớn cả trận đánh nhảy
sang một vùng không gian mới với luật riêng.

Màn chơi được vẽ bằng ký tự braille nên độ phân giải cao gấp 8 lần chữ thường:
vòng tròn tròn, tàu xoay mượt, mọi thứ di chuyển trơn trên màn hình.

```
╭─ SCORE 3260 ─ ▲ ▲ ────────────────────── WAVE 3  ◆◆◆◆◆ ─────────────────────────────── HIGH 8420 ╮
│⠄⡀                   ⠱⡀  ⣀⠤⠊                                                    ⢀⠔⢩⠐⠢⡀     ⡇ ⢀ ⡄  │
│⠈⠐⠊⠔⡠                 ⠱⠒⠉                         ⠠                           ⢠⠊⠁ ⢑⣠⣠⡊    ⠠⣸⠘⠈⠈   │
│    ⠐⠌⠐⡀                ⠐                                         ⠄          ⢠⠃  ⡀⠤⡢⠠⠊ ⢀⠐⡘⠁⡈⡆     │
│      ⢑ ⢂                                                                    ⢇  ⠐⡁ ⢈⠂ ⢀⠂⠅  ⢰⠁⣀⠤⣀  │
│0⠒⠢⡄⠄  ⢂ ⠄                                       ⠁                           ⠈⢆  ⠁⠒⠁  ⠄⠌⣀⡤⠴⢧⠎⣰⢒⢤  │
│⠖  ⠚⣄  ⠰ ⠡      ⠁                            ⣀⣀⡀                              ⠈⠒⠤⣀ ⣀⣀⢬⠔⡋⠁  ⠜⡜⠕⠋⠳  │
│⣥⡾⠤⠊⠄  ⠨ ⢐                                ⣀⡠⠼⠤⠤⠼⠤⣀⡀                               ⠉ ⢠⢚ ⡂⠠⢄⣲⢅⢳⡺⠵⣶  │
│⢖     ⠠⠁ ⠄                        ⠄      ⠸⣅⡄     ⣄⡽                  ⠂              ⡌⠠ ⠐⣁⠤⣞⣿⣗⠾⣽⠐  │
│  ⢀  ⡀⠊ ⠠⠁                        ⠠     «   SHIP LOST   »                           ⠣ ⠡⠐⡵⢵⠈⠿⢲⢅⢁⡩  │
│ ⠁⡀⠄⠊  ⠄⠁                                                                        ⠁  ⠘⢄ ⡥⠁⠁⠂⢅⠁     │
│⠐⠈  ⢀⠠⠈                                                                              ⡘⠛⢄⡈⠠⢀ ⠈⠐⣐⠖  │
│⡀⡀⠠⠐   ⡀                                                                                ⠈⠁⠑⠒⠡⢉ ⡀  │
│                                                                                 ⠐                │
│                      ⡀                    ⠈                                    ⠤                 │
│                    ⣀⠤⠒⠒⠢⠤⠤⣀                                                                      │
│               ⠄  ⡖⠉  ⡔⠐⡦⠒⠢ ⠉⠒⢄                                                               ⢀   │
│                  ⢣   ⢅⢀⠕⣁⣔⠁  ⠈⠢⡀               ⠐                                                 │
│      ⢀           ⢸      ⠇⣀⠕    ⢑⠄                                                                │
│                   ⢣          ⢀⠔⠁                                           ⠄                     │
│                    ⠣⡀      ⣀⠔⠁       ⠈                                            ⡠⠤⠔⠒⠒⠒⠒⢲       │
╰─ ARCADE ────────── ↑↓←→ fly  YUBN diagonal  auto guns  X warp  M model  Q quit ───────── WARP ▰▰▰▰ ╯
```

*(English below)*

## Chạy game

```sh
python3 spacewar.py
```

Cần Python 3.8 trở lên và một terminal ít nhất 40×12. Cửa sổ càng lớn sân chơi
càng rộng. Terminal nhỏ vẫn chơi đúng game đó, chỉ là nhìn từ xa hơn.

Tuỳ chọn:

| Cờ                | Tác dụng                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `--sector NAME`   | bắt đầu ngay ở map `nebula`, `debris`, `mines` hoặc `star` để thử map     |
| `--mute`          | tắt tiếng chuông terminal                                                |
| `--fps 30`        | ép tốc độ vẽ; mặc định game tự chọn                                      |

**Nếu game giật:** một số terminal vẽ braille chậm. Game tự phát hiện khi
lệnh vẽ tốn thời gian, hạ xuống 30 khung/giây và báo `DRAW 30` ở màn hình
chờ; mô phỏng và điều khiển vẫn chạy 60 Hz.

Riêng **Terminal.app của macOS** thì chậm mà không báo, vì font Menlo mặc định
không có bộ chữ braille nên mỗi ô phải mượn font khác. Game mặc định vẽ 30
khung/giây ở đó. Để mượt hơn: đổi font trong profile sang một font có braille,
như JetBrains Mono, Fira Code, Iosevka hay Cascadia Code, rồi chạy với
`--fps 60`. Hoặc dùng iTerm2, Ghostty, kitty, WezTerm. Ba cái sau còn báo cho
game biết khi bạn nhả phím, nên tàu dừng đúng lúc thay vì phải đoán; màn hình
chờ hiện `KEYS exact` khi có điều đó.

## Phím

| Phím               | Tác dụng                                                          |
| ------------------ | ----------------------------------------------------------------- |
| `↑ ↓ ← →` / `WASD` | giữ để bay (arcade) · xoay, đẩy, hãm (classic)                    |
| `Y` `U` `B` `N`    | bay chéo bằng một phím: trên-trái, trên-phải, dưới-trái, dưới-phải |
| `Space`            | vào trận, từ màn hình chờ hoặc sau khi thua                        |
| `0`                | dừng hẳn                                                          |
| `X`                | nhảy không gian tới chỗ khác, hồi 3 giây                          |
| `Z`                | thả bom: xoá mọi đạn địch, làm đau mọi tàu trên màn hình          |
| `-` `=`            | thu nhỏ / phóng to mọi thứ, 50%–140%, được lưu lại                 |
| `M`                | đổi kiểu bay                                                      |
| `P`                | tạm dừng                                                          |
| `R`                | chơi lại                                                          |
| `Q`                | thoát                                                             |

## Hai kiểu bay

**ARCADE** (mặc định): phím mũi tên ra lệnh hướng bay. Giữ thì bay, thả thì
dừng. Dễ vào, hợp với terminal.

**CLASSIC**: kiểu Asteroids 1979. `←→` xoay, `↑` đẩy theo mũi tàu, `↓` hãm nhẹ.
Không có phanh, tàu trôi theo quán tính.

Nhấn `M` để đổi bất cứ lúc nào. Lựa chọn và điểm cao được lưu trong
`.spacewar_state` cạnh file game.

## Súng tự bắn, bay là ngắm

Bạn không nhấn gì để bắn. Súng bắn liên tục theo hướng mũi tàu, mũi tàu quay
theo hướng bạn bay. Muốn bắn trúng thì lái tàu hướng về mục tiêu. Đạn tắt khi
chạm mép màn hình.

## Mục tiêu

Diệt hết hạm đội của mỗi wave. Ba mạng, thêm một mạng mỗi 20.000 điểm.

| Mục tiêu                                       | Máu | Điểm   |
| ---------------------------------------------- | --- | ------ |
| Đá lớn / vừa / nhỏ                              | 1   | 20 / 50 / 100 |
| Interceptor: nhanh, mỏng, bắn thẳng vào bạn     | 1   | 150    |
| Gunship: bắn đón đầu, đổi hướng sau khi nó bắn  | 2   | 400    |
| Tender: tàu tiếp tế không súng, chạy trốn, luôn rơi 2 đồ | 3 | 600 |
| **Marauder**: boss nhỏ, mỗi wave 5, lao thẳng vào bạn | 11 | 2.500 |
| **Dreadnought**: boss lớn, mỗi wave 10, dưới nửa máu bắn vòng lửa | 28 | 12.000 |

Boss có nhiều kiểu bắn thay phiên: quạt, chuỗi bám, quét ngang, cặp lao, xoáy,
tường đạn. Cách né lần trước không hẳn là cách né lần này.

**Chuỗi hạ tàu**: hạ liên tiếp để nhân điểm ×2 sau 3 tàu, ×3 sau 6, tối đa ×5.
Năm giây không hạ ai hoặc mất mạng thì về ×1.

**Đá là vũ khí**, và chỉ có ở map Debris Field: bắn vỡ đá, hai mảnh bay theo
hướng đạn, nóng đỏ, và làm đau tàu địch đầu tiên nó chạm. Đá cũng chặn đạn cả
hai bên.

## Đồ nhặt

Xác tàu rơi đồ. Bay qua để nhặt. Hình lục giác là băng đạn, hình thoi là trang bị.

| Băng đạn      | Tác dụng                              |
| ------------- | ------------------------------------- |
| **S** SPREAD  | quạt 3 viên                           |
| **R** RAPID   | bắn rất nhanh                         |
| **P** LANCE   | xuyên qua nhiều tàu                   |
| **H** SEEKER  | tự tìm tàu gần nhất                   |
| **G** GAUSS   | mỗi viên 3 máu, hạ gunship một phát   |

| Trang bị           | Tác dụng                                     |
| ------------------ | -------------------------------------------- |
| **O** SHIELD       | chịu một đòn rồi mất                          |
| **\*** BOMB        | giữ tối đa 3, nhấn `Z` để dùng               |
| **+** EXTRA SHIP   | thêm một mạng                                |

## Các map

Mười wave đầu là không gian trống. Từ wave 11, sau mỗi Dreadnought, trận đánh
nhảy sang một map khác, thứ tự đổi mỗi lần chơi.

| Map              | Luật                                                                    |
| ---------------- | ----------------------------------------------------------------------- |
| **NEBULA**       | tầm nhìn ngắn: ngoài tầm cảm biến, tàu địch chỉ là chấm nhấp nháy, đạn địch là đốm mờ. Đạn của bạn luôn thấy rõ |
| **DEBRIS FIELD** | map duy nhất có thiên thạch: nhiều, to, và đá mới liên tục trôi vào     |
| **MINEFIELD**    | mìn cảm ứng trôi khắp map, nổ khi tàu nào tới gần hoặc khi bạn bắn. Bắn mìn cạnh địch là ý đồ chính |
| **GRAVITY WELL** | ngôi sao ở giữa hút mọi thứ. Vòng đứt nét quanh nó là điểm không thể quay lại, đừng vượt qua. Chạm sao là chết, khiên sẽ hất bạn ra |

## Dành cho người phát triển

```sh
python3 -m unittest test_spacewar     # bộ test
python3 spacewar.py --selftest        # chạy 2.600 khung không cần terminal
python3 spacewar.py --keytest         # xem terminal gửi gì khi giữ phím
```

Mã nguồn nằm trong thư mục `game/`, mỗi module một việc: `config.py` thông số,
`screen.py` bộ đệm braille, `hulls.py` hình tàu, `entities.py` tàu và đạn,
`fleet.py` hạm đội, `sectors.py` các map, `render.py` vẽ, `game.py` mô phỏng,
`input.py` bàn phím.

---

# English

A space combat game that runs in your terminal, in pure Python with no
dependencies. You fly one ship against a hostile fleet, with a mini boss every
fifth wave and a boss every tenth, and after every boss the whole fight jumps
to a new region of space with one rule of its own.

The play field is drawn in braille characters, which gives 8× the resolution
of ordinary text: circles are round, rotation is smooth, and everything moves
sub-character.

## Run

```sh
python3 spacewar.py
```

Python 3.8+ and any terminal at least 40×12. A bigger window is a bigger
field. A small terminal plays the same game, seen from further away.

| Flag              | Effect                                                              |
| ----------------- | ------------------------------------------------------------------- |
| `--sector NAME`   | start in `nebula`, `debris`, `mines` or `star`, to try a sector      |
| `--mute`          | turn off the terminal bell                                          |
| `--fps 30`        | pin the draw rate; by default the game picks it                     |

**If it stutters:** some terminals are slow to draw braille. The game
notices when a draw takes too long, drops to 30 frames a second and says
`DRAW 30` on the title screen; the simulation and the controls stay at 60 Hz.

**macOS Terminal.app** is slow without showing it, because its default Menlo
font has no braille glyphs and every cell falls back to another face. The
game draws at 30 there by default. For better: switch the profile's font to
one with braille, such as JetBrains Mono, Fira Code, Iosevka or Cascadia Code,
and run with `--fps 60`. Or use iTerm2, Ghostty, kitty or WezTerm; the last
three also tell the game when you release a key, so the ship stops exactly
when you do instead of on a guess. The title screen shows `KEYS exact` then.

## Controls

| Key                | Action                                                      |
| ------------------ | ----------------------------------------------------------- |
| `↑ ↓ ← →` / `WASD` | hold to fly (arcade) · turn, thrust, retro-burn (classic)   |
| `Y` `U` `B` `N`    | one-key diagonals: up-left, up-right, down-left, down-right |
| `Space`            | launch, from the title screen or after a game over          |
| `0`                | all stop                                                    |
| `X`                | hyperspace: jump somewhere else, 3s cooldown                |
| `Z`                | bomb: every hostile round gone, every hull hurt             |
| `-` `=`            | smaller / bigger, 50%–140%, saved                           |
| `M`                | switch flight model                                         |
| `P`                | pause                                                       |
| `R`                | restart                                                     |
| `Q`                | quit                                                        |

## Two flight models

**ARCADE** (default): the arrows command a direction. Hold to fly, let go to
stop. Easy to pick up, and it suits a terminal.

**CLASSIC**: the 1979 model. `←→` rotate, `↑` thrusts along the nose, `↓` is a
weak retro burn. No brakes; momentum is yours.

Press `M` any time to swap. Your choice and high score are saved in
`.spacewar_state` next to the script.

## The gun fires itself, flying is aiming

You press nothing to shoot. The gun fires continuously along the nose, and the
nose follows the way you fly. To hit something, fly toward it. Rounds die at
the edge of the screen.

## Goal

Destroy each wave's fleet. Three lives, an extra one every 20,000 points.

| Target                                                     | Hull | Points        |
| ---------------------------------------------------------- | ---- | ------------- |
| Large / medium / small asteroid                            | 1    | 20 / 50 / 100 |
| Interceptor: fast, fragile, shoots at where you are        | 1    | 150           |
| Gunship: leads its shots, change course after it fires     | 2    | 400           |
| Tender: unarmed hauler, runs, always drops two pickups     | 3    | 600           |
| **Marauder**: mini boss, every 5th wave, charges you       | 11   | 2,500         |
| **Dreadnought**: boss, every 10th wave, rings of fire under half hull | 28 | 12,000 |

Bosses cycle through several volley shapes: fan, tracking burst, sweep,
lance, spiral, wall. The dodge that worked last time is not the dodge for
this one.

**The chain**: consecutive kills multiply your score, ×2 after three, ×3 after
six, up to ×5. Five seconds without a kill, or a lost ship, resets it.

**Rocks are ammunition**, and they exist only in the Debris Field: shoot a
rock and its two fragments fly off along your shot, hot, hurting the first
hull they meet. Rocks also stop rounds from both sides.

## Pickups

Wrecks drop salvage; fly over it. A hexagon is a magazine, a diamond is gear.

| Magazine      | Effect                                  |
| ------------- | --------------------------------------- |
| **S** SPREAD  | a fan of three                          |
| **R** RAPID   | very fast fire                          |
| **P** LANCE   | passes through hulls                    |
| **H** SEEKER  | homes on the nearest ship               |
| **G** GAUSS   | three hull points a slug, one-shots a gunship |

| Gear               | Effect                               |
| ------------------ | ------------------------------------ |
| **O** SHIELD       | eats one hit, then is gone            |
| **\*** BOMB        | hold up to three, `Z` to use         |
| **+** EXTRA SHIP   | one more life                        |

## Sectors

The first ten waves are open space. From wave 11, after every Dreadnought,
the fight jumps to another sector, in a different order every run.

| Sector           | Rule                                                                    |
| ---------------- | ----------------------------------------------------------------------- |
| **NEBULA**       | short sensor range: past it a hostile is a blinking dot and its rounds faint specks. Your own shots you always see |
| **DEBRIS FIELD** | the only sector with asteroids: many, big, and fresh ones keep drifting in |
| **MINEFIELD**    | proximity mines adrift everywhere, set off by any hull or by your shots. Shooting one next to an enemy is the idea |
| **GRAVITY WELL** | a star at the centre pulls on everything. The dashed ring round it is the point of no return, stay outside it. Touch the star and you are gone; a shield throws you clear |

## For developers

```sh
python3 -m unittest test_spacewar     # the test suite
python3 spacewar.py --selftest        # 2,600 headless frames, no terminal needed
python3 spacewar.py --keytest         # what your terminal sends while you hold a key
```

The code lives in `game/`, one job per module: `config.py` tunables,
`screen.py` the braille buffer, `hulls.py` ship silhouettes, `entities.py`
ships and rounds, `fleet.py` the hostile fleet, `sectors.py` the sectors,
`render.py` drawing, `game.py` the simulation, `input.py` the keyboard.
