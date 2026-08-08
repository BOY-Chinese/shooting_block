import pygame as pg
import math
import random as rd

class MoveState:
    FREE = 0  # 自由落体
    MOVE = 1  # 微调
    STAY = 2  # 静止
    FALL = 3  # 下落
    TRIP = 4  # 三消

class Block(pg.sprite.Sprite):
    def __init__(self, pos, image, level, target_pos,grid_pos=None,speed=[0.2,-0.3]):
        super().__init__()
        self.image = image
        self.pos = list(pos)  # 使用列表表示坐标，便于修改
        self.rect = self.image.get_rect(center=self.pos)
        self.target_pos = list(target_pos)
        self.level = level
        self.max_level=5
        self.speed = speed
        self.acc = [0, 0.0002]
        self.move_state = MoveState.FREE
        self.grid_pos = grid_pos
        self.locked = False  # 锁定状态，用于防止升级过程中的重复操作
        self.run_time = 0  # 用于三消动画计时
        #音频
        pg.mixer.init()
        self.sfx_dict={
            'hit':pg.mixer.Sound('snd\hit_music.wav'),
            'level_up':pg.mixer.Sound('snd\level_up_music.wav'),
            'trip':pg.mixer.Sound('snd\TRIP_music.wav')
        }

    def set_locked(self, locked):
        """锁定接口，防止方块在升级过程中被重复选中"""
        self.locked = locked

    def update(self, delta_time, screen_width, screen_height):
        if self.move_state == MoveState.FREE:
            # 自由下落状态：根据加速度更新位置
            self.speed[0] += self.acc[0] * delta_time
            self.speed[1] += self.acc[1] * delta_time
            self.pos[0] += self.speed[0] * delta_time
            self.pos[1] += self.speed[1] * delta_time
            self.rect.center = self.pos

            # 碰撞边界反弹
            if self.pos[0] < 0 or self.pos[0] > screen_width:
                self.sfx_dict['hit'].play()
                self.speed[0] *= -1
            if self.pos[1] < 0:
                self.sfx_dict['hit'].play()
                self.speed[1] *= -1

        elif self.move_state == MoveState.MOVE:
            # 微调至目标位置
            dx = self.target_pos[0] - self.pos[0]
            dy = self.target_pos[1] - self.pos[1]
            self.pos[0] += dx / 5
            self.pos[1] += dy / 5
            if abs(dx) < 1 and abs(dy) < 1:
                self.pos = list(self.target_pos)
                self.move_state = MoveState.STAY
            self.rect.center = self.pos

        elif self.move_state == MoveState.FALL:
            # 垂直下落状态
            self.pos[0] += (self.target_pos[0] - self.pos[0]) / 5
            self.speed[1] += self.acc[1] * delta_time
            self.pos[1] += self.speed[1] * delta_time
            if self.pos[1] >= self.target_pos[1]:
                self.pos = self.target_pos
                self.move_state = MoveState.STAY
            self.rect.center = self.pos
        
        elif self.move_state == MoveState.TRIP:
            #三消动画
            self.sfx_dict['trip'].play()
            self.pos[0]-=delta_time/10
            self.pos[1]+=5*(2.5-self.run_time)
            self.run_time-=delta_time/1000
            if self.run_time<=0:
                self.move_state=MoveState.STAY
                self.locked=False
            self.rect.center = self.pos


class BlockLauncher:
    def __init__(self):
        pg.init()
        self.delta_time = 0
        self.launch_blocks = pg.sprite.Group()     # 正在发射的方块
        self.receive_blocks = {}                   # 已经落地/碰撞的方块
        self.remove_blocks = {}                    # 升级前暂存区
        self.running = True
        self.font=pg.font.Font(None,199)
        self.show_score=0
        self.curr_score=0
        # 屏幕设置
        self.screen_width, self.screen_height = 1408, 704
        self.back_image = pg.transform.scale(
            pg.image.load('pic/background.png'),
            (64, 64)
        )
        self.screen = pg.display.set_mode((self.screen_width, self.screen_height))

        # 背景网格生成
        self.back_blocks = {}
        for i in range(self.screen_height // 64):
            for j in range(self.screen_width // 64):
                rect = pg.Rect(self.screen_width // 2 + j * 64, i * 64, 64, 64)
                self.back_blocks[(i, j)] = rect
                self.receive_blocks[(i, j)] = None

        # 加载方块图片
        images = []
        for x in [2, 4, 8, 16, 32, 64]:
            img = pg.transform.scale(
                pg.image.load(f'pic/block_{x}.png'),
                (64, 64)
            )
            images.append(img)
        self.images = images

    def level_up(self, block):
        """将方块等级提升一级"""
        if block.locked:
            return False
        if block.level < 5:
            block.sfx_dict['level_up'].play()
            block.level += 1
            block.image = self.images[block.level]
            return True
        return False

    def add_block(self, pos, speed):
        """添加一个发射状态的新方块"""
        rad = self.calc_degree([0, self.screen_height], pos)
        level = rd.randint(0, 2)
        block = Block([0, self.screen_height], self.images[level], level, pos,speed=speed)
        block.speed[0] += math.cos(rad) * 0.3
        block.speed[1] += math.sin(rad) * 0.3
        self.launch_blocks.add(block)

    def set_move_state(self, block, move_state, grid_pos=None,run_time=None):
        """设置方块状态和目标位置"""
        block.move_state = move_state
        block.grid_pos = grid_pos
        block.run_time=run_time
        if grid_pos:
            target_x = grid_pos[1] * 64 + 32 + self.screen_width // 2   # 计算X轴目标中心点
            target_y = grid_pos[0] * 64 + 32                            # 计算Y轴目标中心点
            block.target_pos = [target_x, target_y]

    def move_right_all_blocks(self):
        """将所有静止的方块尽可能地向右靠拢"""
        max_col = self.screen_width // 64 // 2
        max_row = self.screen_height // 64
        for i in range(max_row):
            last_col=max_col-1
            for j in range(max_col-1,-1,-1):
                rb=self.receive_blocks.get((i,j))
                if not rb:
                    continue
                if j==last_col:
                    last_col-=1
                    continue
                self.set_move_state(rb,MoveState.MOVE,(i,last_col))
                self.receive_blocks[(i,last_col)]=rb
                self.receive_blocks[(i,j)]=None
                last_col-=1

    def move_left_all_blocks(self):
        """将所有静止的方块尽可能地向左靠拢"""
        max_col = self.screen_width // 64 // 2
        max_row = self.screen_height // 64
        for i in range(max_row):
            begin_col=0
            for j in range(max_col):
                rb=self.receive_blocks.get((i,j))
                if not rb:
                    continue
                if j==begin_col:
                    begin_col+=1
                    continue
                self.set_move_state(rb,MoveState.MOVE,(i,begin_col))
                self.receive_blocks[(i,begin_col)]=rb
                self.receive_blocks[(i,j)]=None
                begin_col+=1

    def update_blocks(self):
        """更新所有发射中的方块位置，并检查是否要转入 receive_blocks"""
        for block in self.launch_blocks.sprites():
            block.update(self.delta_time, self.screen_width, self.screen_height)
            grid_i = int(block.pos[1] // 64)
            grid_j = int((block.pos[0] - self.screen_width // 2) // 64)
            grid_ij = (grid_i, grid_j)

            # 判断是否到达底部或与其他方块碰撞
            if block.pos[1] >= self.screen_height - 64 and block.pos[0] >= self.screen_width // 2:
                self.set_move_state(block, MoveState.MOVE, grid_ij)
                self.receive_blocks[grid_ij] = block
                self.launch_blocks.remove(block)
            else:
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        bk = self.receive_blocks.get((grid_i + dy, grid_j + dx))
                        if bk and bk.rect.colliderect(block.rect):
                            if grid_j >= 0:
                                self.set_move_state(block, MoveState.MOVE, grid_ij)
                                self.receive_blocks[grid_ij] = block
                                self.launch_blocks.remove(block)
                            else:
                                block.speed[0] = 0

        # 处理该下落的方块
        max_col = self.screen_width // 64 // 2
        max_row = self.screen_height // 64

        for j in range(max_col):
            last_row = max_row - 1
            for i in range(max_row - 1, -1, -1):
                rb = self.receive_blocks.get((i, j))
                if not rb:
                    continue
                if i == last_row:
                    last_row -= 1
                    continue
                if rb.move_state != MoveState.FALL:
                    self.set_move_state(rb, MoveState.FALL, (last_row, j))
                    self.receive_blocks[(last_row, j)] = rb
                    self.receive_blocks[(i, j)] = None
                    last_row -= 1

        # 处理合成逻辑
        for j in range(max_col):
            for i in range(max_row-1,-1,-1):
                rb = self.receive_blocks.get((i, j))
                if not rb or rb.move_state != MoveState.STAY or rb.locked or rb.level==rb.max_level:
                    continue
                for leftup in [(i - 1, j), (i, j - 1)]:
                    lrb = self.receive_blocks.get(leftup)
                    if not lrb or lrb.move_state != MoveState.STAY or lrb.locked:
                        continue
                    if lrb.level != rb.level:
                        continue
                    self.curr_score+=rb.level+1
                    rb.set_locked(True)
                    lrb.set_locked(True)
                    self.set_move_state(lrb, MoveState.MOVE, (i, j))
                    self.remove_blocks[(i, j)] = lrb
                    self.receive_blocks[leftup] = None
                    break
        #处理横向三消逻辑
        for i in range(max_row):
            for j in range(max_col):
                rb=self.receive_blocks.get((i,j))
                if not rb or rb.level!=rb.max_level or rb.move_state!=MoveState.STAY:
                    continue
                cnt=1
                for k in range(1,max_col-j):
                    kb=self.receive_blocks.get((i,j+k))
                    if not kb or kb.level!=kb.max_level or kb.move_state!=MoveState.STAY:
                        break
                    cnt+=1
                if cnt<3:
                    continue
                self.curr_score+=cnt*cnt*cnt*rb.max_level
                for k in range(cnt):
                    kb=self.receive_blocks.get((i,j+k))
                    self.set_move_state(kb,MoveState.TRIP,run_time=3)
                    self.remove_blocks[(i,j+k)]=kb
                    self.receive_blocks[(i,j+k)]=None
                j += cnt  # 跳过已消除的
        #处理垂直三消逻辑
        for j in range(max_col):
            for i in range(max_row):
                rb=self.receive_blocks.get((i,j))
                if not rb or rb.level!=rb.max_level or rb.move_state!=MoveState.STAY:
                    continue
                cnt=1
                for k in range(1,max_row-i):
                    kb=self.receive_blocks.get((i+k,j))
                    if not kb or kb.level!=kb.max_level or kb.move_state!=MoveState.STAY:
                        break
                    cnt+=1
                if cnt<3:
                    continue
                self.curr_score+=cnt*cnt*cnt*rb.max_level
                for k in range(cnt):
                    kb=self.receive_blocks.get((i+k,j))
                    self.set_move_state(kb,MoveState.TRIP,run_time=3)
                    self.remove_blocks[(i+k,j)]=kb
                    self.receive_blocks[(i+k,j)]=None
                i += cnt  # 跳过已消除的

        # 升级方块
        rb_list = [(ij, block) for ij, block in self.remove_blocks.items()]
        for ij, block in rb_list:
            if block:
                block.update(self.delta_time, self.screen_width, self.screen_height)
                if block.move_state == MoveState.STAY:
                    if self.receive_blocks[ij]:
                        self.receive_blocks[ij].set_locked(False)
                        self.level_up(self.receive_blocks[ij])
                        del self.remove_blocks[ij]

        # 只对仍在微调的 receive_blocks 方块调用 update
        for block in self.receive_blocks.values():
            if block:
                block.update(self.delta_time, self.screen_width, self.screen_height)

    def calc_degree(self, ori, tar):
        """计算两点之间的角度"""
        dx = tar[0] - ori[0]
        dy = tar[1] - ori[1]
        if dx == 0 and dy == 0:
            return math.atan2(1, 0)
        return math.atan2(dy, dx)

    def draw_blocks(self):
        # 绘制背景格子
        for rect in self.back_blocks.values():
            self.screen.blit(self.back_image, rect)

        # 绘制正在发射的方块
        self.launch_blocks.draw(self.screen)

        # 绘制已接收的方块
        for block in self.receive_blocks.values():
            if block:
                self.screen.blit(block.image, block.rect)

        # 绘制准备移除的方块
        for block in self.remove_blocks.values():
            if block:
                self.screen.blit(block.image, block.rect)
        
        # 显示当前分数
        self.show_score+=self.curr_score
        self.curr_score=0
        text_surface = self.font.render(str(self.show_score), True, (255, 255, 255))
        text_rect=text_surface.get_rect()
        text_rect.x=10
        text_rect.y=10
        self.screen.blit(text_surface, text_rect)


    def run(self):
        clock = pg.time.Clock()
        pg.mixer.music.load('snd/background_music.wav')
        pg.mixer.music.set_volume(0.5)
        pg.mixer.music.play(-1)
        while self.running:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False
                elif event.type == pg.MOUSEBUTTONDOWN:
                    for i in range(1):
                        speed=[0.2+i/10,-0.3-i/10]
                        self.add_block(event.pos,speed)
                elif event.type == pg.KEYDOWN:
                    if event.key == pg.K_d:  # 按下 D 键触发右移
                        self.move_right_all_blocks()
                    elif event.key==pg.K_a:   #按下 A 键触发左移
                        self.move_left_all_blocks()

            self.screen.fill((0, 0, 0))
            self.update_blocks()
            self.draw_blocks()
            pg.display.flip()
            self.delta_time = clock.tick(120)


# 启动游戏
if __name__ == "__main__":
    game = BlockLauncher()
    game.run()