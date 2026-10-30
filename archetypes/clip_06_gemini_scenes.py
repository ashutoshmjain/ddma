import numpy as np
from numpy import cos, sin, pi
from manim_compat import *


# (Using universal get_footer_and_title from manim_compat)



# CANVAS CONFIGURATION

def get_footer(*args, **kwargs):
    class _DummyScene:
        def add(self, *a, **k): pass
        def play(self, *a, **k): pass
    scene = next((a for a in args if hasattr(a, 'play')), _DummyScene())
    self = scene
    str_args = [a for a in args if isinstance(a, str)]
    title_text = kwargs.get('title_text') or kwargs.get('title_str') or (str_args[0] if len(str_args) >= 1 else 'AI AUTONOMY')
    category_text = kwargs.get('category_text') or kwargs.get('category') or (str_args[1] if len(str_args) >= 2 else (str_args[0] if len(str_args) == 1 else 'ECONOMIC AUTONOMY'))
    category = category_text
    category_name = category_text
    category_label = category_text
    title_str = title_text
    text_str = title_text

    footer_line = Line(LEFT * 3.5, RIGHT * 3.5, color="#FFFFFF", stroke_width=1.5).move_to(DOWN * 3.35)
    footer_line.set_opacity(0.4)
    left_text = Text(category, font="Arial", weight=BOLD, font_size=10, color="#FFFFFF").set_opacity(0.65).next_to(footer_line, DOWN, buff=0.12).to_edge(LEFT, buff=0.55)
    right_text = Text("DEEP DIVE PODCAST • EP. 248", font="Arial", weight=NORMAL, font_size=10, color="#FFFFFF").set_opacity(0.65).next_to(footer_line, DOWN, buff=0.12).to_edge(RIGHT, buff=0.55)
    scene.add(footer_line, left_text, right_text)

def get_title(scene, text="PERISHABLE COMPUTE !"):
    title = Text(text, font="Arial", weight=BOLD, font_size=20, color="#FFFFFF").move_to([0, -2.95, 0])
    return title

class Scene06_01(Scene):
    def construct(self):
        get_footer(self)
        title = get_title(self)
        
        # Visual: Server rack with a ticking clock above it
        server = RoundedRectangle(width=1.5, height=2.0, corner_radius=0.1, color="#FFFFFF", stroke_width=2).move_to(DOWN * 1.0)
        slots = VGroup(*[Line(LEFT*0.5, RIGHT*0.5, color="#FFFFFF", stroke_width=1).move_to(server.get_center() + UP*(0.6 - i*0.4)) for i in range(4)])
        clock = Circle(radius=0.5, color="#FFFFFF", stroke_width=2).move_to(UP * 0.1)
        hand = Line(clock.get_center(), clock.get_center() + UP * 0.4, color="#FFFFFF", stroke_width=3)
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(server), Create(slots), Create(clock), Create(hand), run_time=1.0)
        self.play(Rotate(hand, angle=-6*PI, about_point=clock.get_center()), server.animate.set_opacity(0.3), run_time=5.4, rate_func=linear)
        self.play(FadeOut(VGroup(server, slots, clock, hand, title)), run_time=0.6)

class Scene06_02(Scene):
    def construct(self):
        get_footer(self)
        title = get_title(self)
        
        # Visual: Hourglass with compute blocks falling
        top_tri = Polygon([-1, 0.4, 0], [1, 0.4, 0], [0, -0.6, 0], color="#FFFFFF", stroke_width=2)
        bot_tri = Polygon([-1, -1.6, 0], [1, -1.6, 0], [0, -0.6, 0], color="#FFFFFF", stroke_width=2)
        block = Rectangle(width=0.3, height=0.2, color="#FFFFFF", fill_opacity=1).move_to([0, 0.1, 0])
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(top_tri), Create(bot_tri), run_time=1.0)
        
        # Falling blocks animation
        for i in range(5):
            b = block.copy()
            self.add(b)
            self.play(b.animate.move_to([0, -1.4, 0]).set_opacity(0), run_time=0.9, rate_func=ease_in_sine)
        
        self.play(FadeOut(VGroup(top_tri, bot_tri, title)), run_time=0.5)

class Scene06_03(Scene):
    def construct(self):
        get_footer(self)
        title = get_title(self)
        
        # Visual: A gauge/meter dropping from Full to Empty
        gauge = Arc(radius=1.8, start_angle=0, angle=PI, color="#FFFFFF", stroke_width=4).move_to(DOWN * 1.2)
        needle = Arrow(gauge.get_center(), gauge.get_center() + RIGHT * 1.5, buff=0, color="#FFFFFF", stroke_width=5)
        label_f = Text("F", font_size=15, color="#FFFFFF").next_to(gauge, RIGHT, buff=0.1)
        label_e = Text("E", font_size=15, color="#FFFFFF").next_to(gauge, LEFT, buff=0.1)
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(gauge), Create(needle), Write(label_f), Write(label_e), run_time=1.0)
        self.play(Rotate(needle, angle=PI, about_point=gauge.get_center()), run_time=5.4, rate_func=slow_into)
        self.play(FadeOut(VGroup(gauge, needle, label_f, label_e, title)), run_time=0.6)

class Scene06_04(Scene):
    def construct(self):
        get_footer(self)
        title = get_title(self)
        
        # Visual: Server with a "USE BY" stamp
        server = RoundedRectangle(width=2.5, height=1.5, color="#FFFFFF", stroke_width=2).move_to(DOWN * 0.8)
        label = Text("COMPUTE UNIT", font_size=15, color="#FFFFFF").move_to(server.get_center())
        stamp_box = Rectangle(width=1.8, height=0.6, color="#FFFFFF", stroke_width=3).move_to(DOWN * 0.8).set_opacity(0)
        stamp_text = Text("EXPIRED", font="Arial", weight=BOLD, font_size=24, color="#FFFFFF").move_to(stamp_box.get_center()).set_opacity(0)
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(server), Write(label), run_time=1.0)
        self.wait(1.0)
        self.play(
            stamp_box.animate.set_opacity(1).scale(1.2),
            stamp_text.animate.set_opacity(1).scale(1.2),
            run_time=0.4, rate_func=bounce_it
        )
        self.play(VGroup(server, label, stamp_box, stamp_text).animate.set_opacity(0.2), run_time=4.0)
        self.play(FadeOut(VGroup(server, label, stamp_box, stamp_text, title)), run_time=0.6)

class Scene06_05(Scene):
    def construct(self):
        get_footer(self)
        title = get_title(self)
        
        # Visual: Conveyor belt moving compute blocks into a trash bin
        belt = Line(LEFT * 2.5, RIGHT * 1.5, color="#FFFFFF", stroke_width=2).move_to(DOWN * 1.5)
        wheels = VGroup(Circle(radius=0.2).move_to(LEFT*2.3 + DOWN*1.7), Circle(radius=0.2).move_to(RIGHT*1.3 + DOWN*1.7))
        bin_poly = Polygon([1.8, -1.2, 0], [2.8, -1.2, 0], [2.6, -2.2, 0], [2.0, -2.2, 0], color="#FFFFFF", stroke_width=2)
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(belt), Create(wheels), Create(bin_poly), run_time=1.0)
        
        for i in range(3):
            block = Rectangle(width=0.6, height=0.4, color="#FFFFFF", fill_opacity=0.5).move_to(LEFT * 2.5 + UP * 0.2 + DOWN * 1.5)
            self.add(block)
            self.play(
                block.animate.move_to(RIGHT * 2.3 + DOWN * 1.3).set_opacity(0),
                wheels.animate.rotate(-PI),
                run_time=1.8, rate_func=linear
            )
        
        self.play(FadeOut(VGroup(belt, wheels, bin_poly, title)), run_time=0.6)

class Scene06_06(Scene):
    def construct(self):
        get_footer(self)
        title = get_title(self)
        
        # Visual: Battery icon draining
        battery_body = Rectangle(width=3.0, height=1.5, color="#FFFFFF", stroke_width=3).move_to(DOWN * 1.0)
        battery_tip = Rectangle(width=0.3, height=0.6, color="#FFFFFF", fill_opacity=1).next_to(battery_body, RIGHT, buff=0)
        charge = Rectangle(width=2.8, height=1.3, color="#FFFFFF", fill_opacity=0.8).move_to(battery_body.get_center())
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(battery_body), Create(battery_tip), FadeIn(charge), run_time=1.0)
        self.play(charge.animate.scale(0.01, about_edge=LEFT).set_opacity(0), run_time=5.4, rate_func=linear)
        self.play(FadeOut(VGroup(battery_body, battery_tip, charge, title)), run_time=0.6)

class Scene06_07(Scene):
    def construct(self):
        get_footer(self)
        title = get_title(self)
        
        # Visual: A server inside a melting ice cube
        ice_cube = RoundedRectangle(width=2.2, height=2.2, corner_radius=0.4, color="#FFFFFF", stroke_width=2).move_to(DOWN * 1.0)
        server_core = Rectangle(width=1.0, height=0.6, color="#FFFFFF", fill_opacity=1).move_to(ice_cube.get_center())
        drips = VGroup(Circle(radius=0.05, fill_opacity=1).move_to(DOWN*2.1 + LEFT*0.5), Circle(radius=0.05, fill_opacity=1).move_to(DOWN*2.1 + RIGHT*0.3))
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(ice_cube), Create(server_core), run_time=1.0)
        
        self.play(
            ice_cube.animate.scale(0.4).set_opacity(0.2),
            server_core.animate.set_opacity(0.1),
            drips.animate.shift(DOWN * 0.5).set_opacity(0),
            run_time=5.4, rate_func=linear
        )
        self.play(FadeOut(VGroup(ice_cube, server_core, drips, title)), run_time=0.6)

# Configuration for 740x740 Square Video

def get_footer(*args, **kwargs):
    class _DummyScene:
        def add(self, *a, **k): pass
        def play(self, *a, **k): pass
    scene = next((a for a in args if hasattr(a, 'play')), _DummyScene())
    self = scene
    str_args = [a for a in args if isinstance(a, str)]
    title_text = kwargs.get('title_text') or kwargs.get('title_str') or (str_args[0] if len(str_args) >= 1 else 'AI AUTONOMY')
    category_text = kwargs.get('category_text') or kwargs.get('category') or (str_args[1] if len(str_args) >= 2 else (str_args[0] if len(str_args) == 1 else 'ECONOMIC AUTONOMY'))
    category = category_text
    category_name = category_text
    category_label = category_text
    title_str = title_text
    text_str = title_text

    footer_line = Line(LEFT * 3.5, RIGHT * 3.5, color="#FFFFFF", stroke_width=1.5).move_to(DOWN * 3.35)
    footer_line.set_opacity(0.4)
    left_text = Text(category, font="Arial", weight=BOLD, font_size=10, color="#FFFFFF").set_opacity(0.65).next_to(footer_line, DOWN, buff=0.12).to_edge(LEFT, buff=0.55)
    right_text = Text("DEEP DIVE PODCAST • EP. 248", font="Arial", weight=NORMAL, font_size=10, color="#FFFFFF").set_opacity(0.65).next_to(footer_line, DOWN, buff=0.12).to_edge(RIGHT, buff=0.55)
    scene.add(footer_line, left_text, right_text)

class Scene06_15(Scene):
    def construct(self):
        # Title and Footer
        title = Text("PERISHABLE COMPUTE", font="Arial", weight=BOLD, font_size=20, color="#FFFFFF").move_to([0, -2.95, 0])
        get_footer(self, "COMPUTE ECONOMICS")
        
        # Visual: Server Rack with a Clock (Time is running out)
        server = VGroup(
            RoundedRectangle(corner_radius=0.1, height=1.5, width=1.2, color="#FFFFFF", stroke_width=3),
            Line(LEFT*0.4, RIGHT*0.4, color="#FFFFFF").shift(UP*0.3),
            Line(LEFT*0.4, RIGHT*0.4, color="#FFFFFF").shift(ORIGIN),
            Line(LEFT*0.4, RIGHT*0.4, color="#FFFFFF").shift(DOWN*0.3)
        ).move_to(LEFT * 1.2 + DOWN * 1.0)
        
        clock_face = Circle(radius=0.8, color="#FFFFFF", stroke_width=3).move_to(RIGHT * 1.2 + DOWN * 1.0)
        hour_hand = Line(clock_face.get_center(), clock_face.get_center() + UP * 0.5, color="#FFFFFF", stroke_width=4)
        minute_hand = Line(clock_face.get_center(), clock_face.get_center() + RIGHT * 0.6, color="#FFFFFF", stroke_width=2)
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(server), Create(clock_face), Create(hour_hand), Create(minute_hand))
        
        # Animation: Clock spinning fast while server flickers/fades
        self.play(
            Rotate(hour_hand, -2 * PI, about_point=clock_face.get_center()),
            Rotate(minute_hand, -8 * PI, about_point=clock_face.get_center()),
            server.animate.set_opacity(0.2),
            run_time=5.0,
            rate_func=linear
        )
        self.wait(2.0)

class Scene06_16(Scene):
    def construct(self):
        title = Text("VANISHING CAPACITY", font="Arial", weight=BOLD, font_size=20, color="#FFFFFF").move_to([0, -2.95, 0])
        get_footer(self, "COMPUTE ECONOMICS")
        
        # Visual: A CPU chip that is "melting"
        chip = VGroup(
            Square(side_length=1.5, color="#FFFFFF", stroke_width=4),
            *[Line(ORIGIN, UP*0.2, color="#FFFFFF").shift(UP*0.75 + LEFT*(0.6 - i*0.4)) for i in range(4)],
            *[Line(ORIGIN, DOWN*0.2, color="#FFFFFF").shift(DOWN*0.75 + LEFT*(0.6 - i*0.4)) for i in range(4)],
            *[Line(ORIGIN, LEFT*0.2, color="#FFFFFF").shift(LEFT*0.75 + UP*(0.6 - i*0.4)) for i in range(4)],
            *[Line(ORIGIN, RIGHT*0.2, color="#FFFFFF").shift(RIGHT*0.75 + UP*(0.6 - i*0.4)) for i in range(4)]
        ).move_to(UP * -0.5)
        
        drips = VGroup(*[Circle(radius=0.05, color="#FFFFFF", fill_opacity=1).move_to(chip.get_bottom() + RIGHT*x) for x in np.arange(-0.6, 0.7, 0.3)])
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(chip))
        
        # Animation: Drips falling from the chip
        animations = []
        for drip in drips:
            animations.append(drip.animate(rate_func=slow_into).shift(DOWN * 1.5).set_opacity(0))
            
        self.play(AnimationGroup(*animations, lag_ratio=0.2), chip.animate.scale(0.8).set_opacity(0.5), run_time=6.0)
        self.wait(1.0)

class Scene06_17(Scene):
    def construct(self):
        title = Text("TIME-BOUND UTILITY", font="Arial", weight=BOLD, font_size=20, color="#FFFFFF").move_to([0, -2.95, 0])
        get_footer(self, "COMPUTE ECONOMICS")
        
        # Visual: Hourglass with binary code falling
        top_tri = Polygon([-1, 1, 0], [1, 1, 0], [0, 0, 0], color="#FFFFFF", stroke_width=3)
        bot_tri = Polygon([-1, -1, 0], [1, -1, 0], [0, 0, 0], color="#FFFFFF", stroke_width=3)
        hourglass = VGroup(top_tri, bot_tri).move_to(UP * -0.8)
        
        binary_0 = Text("0", font="Courier", font_size=15, color="#FFFFFF").move_to(UP * -0.5)
        binary_1 = Text("1", font="Courier", font_size=15, color="#FFFFFF").move_to(UP * -0.3)
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(hourglass))
        
        # Animation: Binary digits falling through the center
        def fall_binary(mobject):
            mobject.shift(DOWN * 0.1)
            if mobject.get_center()[1] < -1.8:
                mobject.move_to(UP * -0.5 + RIGHT * np.random.uniform(-0.2, 0.2))

        b_stream = VGroup(*[Text(np.random.choice(["0", "1"]), font="Courier", font_size=12).move_to(UP * -0.5 + RIGHT * np.random.uniform(-0.3, 0.3) + UP * np.random.uniform(0, 0.5)) for _ in range(10)])
        
        self.play(FadeIn(b_stream))
        self.play(
            *[m.animate.shift(DOWN * 1.2).set_opacity(0) for m in b_stream],
            run_time=6.0,
            rate_func=linear
        )
        self.wait(1.0)

class Scene06_18(Scene):
    def construct(self):
        title = Text("IDLE LOSS", font="Arial", weight=BOLD, font_size=20, color="#FFFFFF").move_to([0, -2.95, 0])
        get_footer(self, "COMPUTE ECONOMICS")
        
        # Visual: Conveyor belt moving server icons into a trash bin
        belt = Line(LEFT * 2.5, RIGHT * 1.0, color="#FFFFFF", stroke_width=2).shift(DOWN * 1.0)
        wheels = VGroup(Circle(radius=0.15, color="#FFFFFF").move_to(LEFT*2.3 + DOWN*1.2), Circle(radius=0.15, color="#FFFFFF").move_to(RIGHT*0.8 + DOWN*1.2))
        bin_obj = VGroup(
            Line(LEFT*0.5, LEFT*0.4 + DOWN*0.8),
            Line(RIGHT*0.5, RIGHT*0.4 + DOWN*0.8),
            Line(LEFT*0.4 + DOWN*0.8, RIGHT*0.4 + DOWN*0.8)
        ).move_to(RIGHT * 2.0 + DOWN * 1.8)
        
        server_icon = Square(side_length=0.4, color="#FFFFFF", fill_opacity=0.2).move_to(LEFT * 2.0 + DOWN * 0.8)
        
        self.play(FadeIn(title), run_time=0.6)
        self.add(belt, wheels, bin_obj)
        
        # Animation: Servers moving across and falling
        for i in range(3):
            s = server_icon.copy()
            self.add(s)
            self.play(
                s.animate.move_to(RIGHT * 0.8 + DOWN * 0.8),
                run_time=1.5,
                rate_func=linear
            )
            self.play(
                s.animate.move_to(RIGHT * 2.0 + DOWN * 2.0).set_opacity(0),
                run_time=0.5
            )
            
        self.wait(1.0)

class Scene06_19(Scene):
    def construct(self):
        title = Text("EXPIRING RESOURCES", font="Arial", weight=BOLD, font_size=20, color="#FFFFFF").move_to([0, -2.95, 0])
        get_footer(self, "COMPUTE ECONOMICS")
        
        # Visual: A battery meter labeled "COMPUTE" draining rapidly
        battery_shell = RoundedRectangle(corner_radius=0.1, height=1.2, width=2.5, color="#FFFFFF", stroke_width=4).move_to(UP * -0.8)
        battery_tip = Rectangle(height=0.4, width=0.2, color="#FFFFFF", fill_opacity=1).next_to(battery_shell, RIGHT, buff=0)
        
        fill = Rectangle(height=1.0, width=2.3, color="#FFFFFF", fill_opacity=0.8).move_to(battery_shell.get_center())
        label = Text("COMPUTE", font="Arial", weight=BOLD, font_size=15, color="#000000").move_to(fill.get_center())
        
        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(battery_shell), Create(battery_tip), FadeIn(fill), FadeIn(label))
        
        # Animation: Battery draining to zero
        self.play(
            fill.animate.scale(0.01, about_edge=LEFT).set_opacity(0),
            label.animate.set_opacity(0),
            run_time=5.5,
            rate_func=linear
        )
        
        # Final flash of "EXPIRED"
        expired = Text("EXPIRED", font="Arial", weight=BOLD, font_size=30, color="#FFFFFF").move_to(UP * -0.8)
        self.play(Write(expired), run_time=0.5)
        self.wait(1.0)