"""Pip's world: needs, actions and personality.

This file is the "physics" of Pip's life. The exact same rules are written in C
in PipAI/pip_world.h so the brain behaves on the board the way it learned here.
If you change a number here, change it there too (the GitHub test checks they match).

Everything is vectorised with numpy: arrays hold many Pips at once (one per
simulated world) so training is fast.
"""
import numpy as np

STEP_HOURS = 0.05  # one "thought" every 3 minutes

ACTIONS = ["idle", "nap", "eat", "explore", "play", "sing", "hide", "warm_up", "cool_down", "call", "dance", "window"]
IDLE, NAP, EAT, EXPLORE, PLAY, SING, HIDE, WARM_UP, COOL_DOWN, CALL, DANCE, WINDOW = range(12)
N_ACTIONS = len(ACTIONS)

TRAITS = ["curious", "playful", "lazy", "brave", "affectionate"]
NEEDS = ["food", "energy", "fun", "comfort", "social"]
EMOTIONS = ["grumpy", "sulky", "scared", "frustrated"]  # negative feelings: 0 = none, 1 = very

# Orientation: 0 = no sensor, 1 = upright, 2 = tilted, 3 = upside down
N_FEATURES = 40  # 36 + the 4 feelings


class PipState:
    """Pip's inner state (arrays of shape [B])."""

    def __init__(self, B, rng):
        self.food = rng.uniform(0.3, 1.0, B)
        self.energy = rng.uniform(0.3, 1.0, B)
        self.fun = rng.uniform(0.3, 1.0, B)
        self.comfort = rng.uniform(0.3, 1.0, B)
        self.social = rng.uniform(0.3, 1.0, B)
        self.prev_action = np.zeros(B, dtype=np.int64)
        self.repeat = np.zeros(B)
        self.touch_recent = np.zeros(B)
        self.novelty = np.zeros(B)
        self.prev_temp = np.full(B, np.nan)
        self.prev_sound = np.zeros(B)
        self.prev_orient = np.zeros(B, dtype=np.int64)
        for name in EMOTIONS:
            setattr(self, name, np.zeros(B))

    def reset(self, mask, rng):
        n = int(mask.sum())
        for name in NEEDS:
            getattr(self, name)[mask] = rng.uniform(0.3, 1.0, n)
        self.prev_action[mask] = 0
        self.repeat[mask] = 0
        self.touch_recent[mask] = 0
        self.novelty[mask] = 0
        self.prev_temp[mask] = np.nan
        self.prev_sound[mask] = 0
        self.prev_orient[mask] = 0
        for name in EMOTIONS:
            getattr(self, name)[mask] = 0

    def clamp(self):
        for name in NEEDS + EMOTIONS:
            np.clip(getattr(self, name), 0.0, 1.0, out=getattr(self, name))


def observe(st, se):
    """Take in this moment's senses (before deciding). se = dict of arrays."""
    touched = se["touched"].astype(float)
    st.touch_recent = st.touch_recent * 0.7 + touched
    st.social += 0.1 * touched * (1 - 0.7 * st.sulky)  # a sulky Pip barely notices the first pats
    st.fun += 0.03 * touched
    prev_temp = np.where(np.isnan(st.prev_temp), se["temp"], st.prev_temp)
    change = (np.abs(se["temp"] - prev_temp) / 2.0
              + np.abs(se["sound"] - st.prev_sound)
              + (se["orient"] != st.prev_orient).astype(float))
    st.novelty = np.minimum(1.0, change)
    st.clamp()


def features(st, se, tr):
    """The 40 numbers the brain sees. Order must match pip_features() in C."""
    B = st.food.shape[0]
    h = se["hour"]
    orient = np.zeros((B, 4))
    orient[np.arange(B), se["orient"]] = 1.0
    prev = np.zeros((B, N_ACTIONS))
    prev[np.arange(B), st.prev_action] = 1.0
    cols = [
        st.food, st.energy, st.fun, st.comfort, st.social,
        st.grumpy, st.sulky, st.scared, st.frustrated,
        (se["temp"] - 22.0) / 10.0, se["humidity"] / 100.0,
        np.sin(2 * np.pi * h / 24.0), np.cos(2 * np.pi * h / 24.0),
        se["sound"], se["battery"], se["charging"].astype(float),
        np.minimum(st.touch_recent, 1.0),
    ]
    x = np.column_stack(cols + [orient, st.novelty[:, None], tr, prev, (np.minimum(st.repeat, 10) / 10.0)[:, None]])
    assert x.shape[1] == N_FEATURES
    return x


def act(st, se, tr, a):
    """Do the chosen action for one step, plus the world's natural drift."""
    curious, playful, lazy, brave, affectionate = (tr[:, i] for i in range(5))
    T, sound, hour = se["temp"], se["sound"], se["hour"]
    cold = np.clip((18.0 - T) / 8.0, 0, 1)
    hot = np.clip((T - 26.0) / 8.0, 0, 1)
    flip = np.where(se["orient"] == 3, 0.4, np.where(se["orient"] == 2, 0.15, 0.0))
    hiding = (a == HIDE).astype(float)
    noise = sound * 0.5 * (1 - 0.6 * brave) * (1 - 0.5 * hiding)
    env_comfort = np.clip(1.0 - cold - hot - noise - flip * (1 - 0.5 * hiding), 0, 1)
    napping = (a == NAP).astype(float)
    night = ((hour >= 22) | (hour < 7)).astype(float)
    st.prev_hour_day = 1.0 - night  # used by reward(): daytime naps are discouraged
    owner_near = (st.touch_recent > 0.3).astype(float)

    # Natural drift
    st.food -= 0.006 * (1 - 0.5 * napping)
    st.energy -= 0.004 + 0.004 * (se["battery"] < 0.2)
    st.fun -= 0.007  # fun fades fairly fast: Pip needs to DO things
    st.social -= 0.003
    st.comfort += 0.1 * (env_comfort - st.comfort)

    # Action effects
    st.energy += np.where(a == IDLE, 0.002, 0)

    startled = (sound > 0.6).astype(float)
    restless = (st.energy > 0.8).astype(float)  # not tired: napping barely helps and gets boring
    nap_gain = 0.03 * (1 - 0.8 * sound) * (1 + 0.3 * night) * (1 - startled) * (1 - 0.7 * restless)
    st.energy += napping * nap_gain
    st.comfort -= napping * 0.1 * startled
    st.fun -= napping * 0.004 * restless

    eat = (a == EAT).astype(float)
    overfull = (st.food > 0.75).astype(float)  # eating when already fairly full feels bad
    st.food += eat * 0.08
    st.comfort -= eat * 0.08 * overfull

    ex = (a == EXPLORE).astype(float)
    st.fun += ex * (0.04 + 0.04 * curious + 0.05 * st.novelty)
    st.energy -= ex * 0.009
    st.food -= ex * 0.004

    pl = (a == PLAY).astype(float)
    st.fun += pl * (0.05 + 0.04 * playful)
    st.energy -= pl * 0.011
    st.social += pl * 0.03 * owner_near

    sg = (a == SING).astype(float)
    st.fun += sg * 0.015
    st.social += sg * (0.01 + 0.02 * affectionate * owner_near)
    st.energy -= sg * 0.004

    st.fun -= hiding * 0.003

    wu = (a == WARM_UP).astype(float)
    st.comfort += wu * 0.06 * cold
    st.energy -= wu * 0.004

    cd = (a == COOL_DOWN).astype(float)
    st.comfort += cd * 0.06 * hot
    st.energy -= cd * 0.004

    cl = (a == CALL).astype(float)
    st.social += cl * np.where(owner_near > 0, 0.05, 0.005)

    # Dance: big fun for playful Pips, even better with someone watching
    dn = (a == DANCE).astype(float)
    st.fun += dn * (0.035 + 0.02 * playful)
    st.social += dn * 0.04 * owner_near
    st.energy -= dn * 0.012
    st.food -= dn * 0.003

    # Look out the window: calm entertainment; sunshine is cosy in the day, the moon at night
    wn = (a == WINDOW).astype(float)
    day = 1.0 - night
    st.fun += wn * (0.008 + 0.012 * curious * day + 0.005 * night)
    st.comfort += wn * 0.01 * day
    st.energy += wn * 0.001

    # ---- Negative feelings. Each has a cause, fades by itself, and has something that helps.
    touched = se["touched"].astype(float)
    # Grumpy: woken up by pats, or pestered while exhausted. Resting helps. Lazy Pips mind more.
    woken = touched * (st.prev_action == NAP)
    pestered = touched * (st.energy < 0.3) * (st.touch_recent > 1.5)
    resting = ((a == NAP) | (a == IDLE)).astype(float)
    st.grumpy = st.grumpy * (0.85 - 0.15 * resting) + (0.5 * woken + 0.3 * pestered) * (0.6 + 0.8 * lazy)
    # Sulky: left alone while lonely. Fades once Pip feels loved again; pats help a lot.
    lonely_now = ((st.social < 0.2) & (st.touch_recent < 0.05)).astype(float)
    st.sulky = st.sulky * np.where(st.social > 0.4, 0.9, 0.98) + 0.03 * lonely_now * (0.5 + affectionate) - 0.25 * touched
    # Scared: flipped over, tilted, or a sudden loud noise. Hiding helps; brave Pips recover fast.
    flipped = ((se["orient"] == 3) & (st.prev_orient != 3)).astype(float)
    tilted = ((se["orient"] == 2) & (st.prev_orient != 2)).astype(float)
    loud = (sound > 0.7).astype(float)
    st.scared = (st.scared * (0.85 - 0.15 * brave) - 0.15 * hiding
                 + (0.6 * flipped + 0.3 * tilted + 0.5 * loud) * (1.2 - 0.8 * brave))
    # Frustrated: tried to play/dance/explore while too tired, or tried to eat while stuffed.
    failed = (((a == PLAY) | (a == DANCE) | (a == EXPLORE)) & (st.energy < 0.15)).astype(float)
    stuffed = ((a == EAT) & (st.food > 0.95)).astype(float)
    st.frustrated = st.frustrated * 0.8 + 0.3 * failed + 0.2 * stuffed

    st.clamp()
    st.repeat = np.where(a == st.prev_action, st.repeat + 1, 0)
    st.prev_action = a.copy()
    st.prev_temp = se["temp"].copy()
    st.prev_sound = se["sound"].copy()
    st.prev_orient = se["orient"].copy()


def reward(st, tr, a):
    """How good life feels this step. Personality changes what Pip cares about."""
    curious, playful, lazy, brave, affectionate = (tr[:, i] for i in range(5))
    w_food = 1.0
    w_energy = 0.8 + 0.6 * lazy
    w_fun = 0.6 + 0.6 * playful
    w_comfort = 1.0 - 0.3 * brave
    w_social = 0.3 + 0.9 * affectionate
    # Bad feelings feel bad (so Pip learns what makes them go away)
    r_feel = -0.3 * (st.grumpy ** 2 + st.sulky ** 2 + st.scared ** 2 + st.frustrated ** 2)
    r = r_feel - (w_food * (1 - st.food) ** 2 + w_energy * (1 - st.energy) ** 2 + w_fun * (1 - st.fun) ** 2
          + w_comfort * (1 - st.comfort) ** 2 + w_social * (1 - st.social) ** 2)
    # Personality: each trait makes its favourite activity enjoyable in itself,
    # and a LOW trait makes that activity unpleasant (a lazy Pip hates exploring...).
    like = 0.3
    r += like * (curious - 0.5) * (a == EXPLORE)
    r += like * (playful - 0.5) * (a == PLAY)
    r += like * (lazy - 0.5) * (a == NAP)
    r -= like * 0.5 * (lazy - 0.5) * ((a == EXPLORE) | (a == PLAY))
    r += like * (affectionate - 0.5) * ((a == SING) | (a == CALL))
    r += like * (0.5 - brave) * (a == HIDE)
    r += like * 0.5 * (playful - 0.5) * (a == DANCE)
    r += like * 0.25 * (curious - 0.5) * (a == WINDOW)
    # Being active is rewarding in itself, whatever the personality
    # Being active is rewarding in itself (singing is easy, so it counts half; watching isn't active)
    active = (a == EXPLORE) | (a == PLAY) | (a == CALL) | (a == DANCE)
    r += 0.04 * active + 0.02 * (a == SING)
    # Sleeping the day away when not tired, or eating when not hungry, feels lazy
    day = (st.prev_hour_day if hasattr(st, "prev_hour_day") else 1.0)
    r -= 0.04 * ((a == NAP) & (st.energy > 0.6)) * day
    r -= 0.03 * ((a == EAT) & (st.food > 0.7))
    # Real pets don't do one thing forever
    r -= 0.02 * ((st.repeat > 4) & (a != NAP)) + 0.02 * ((st.repeat > 12) & (a == NAP))
    r -= 0.02 * ((st.repeat > 2) & (a == WINDOW))  # staring out of the window gets old fast
    return r


class World:
    """Random rooms, days, noises, owners and batteries for training (Python only)."""

    def __init__(self, B, rng, episode_steps=1440):
        self.B, self.rng, self.episode_steps = B, rng, episode_steps
        self.st = PipState(B, rng)
        self.t = rng.integers(0, episode_steps, B)  # stagger episode starts
        self.last_action = np.zeros(B, dtype=np.int64)
        self._new(np.ones(B, dtype=bool))

    def _new(self, m):
        r, n = self.rng, int(m.sum())
        if n == 0:
            return
        if not hasattr(self, "traits"):
            self.traits = np.zeros((self.B, 5))
            for k in ["base_t", "amp_t", "offset_t", "hum", "hour", "noisy", "battery"]:
                setattr(self, k, np.zeros(self.B))
            for k in ["has_orient", "orient", "owner", "on_usb", "charging"]:
                setattr(self, k, np.zeros(self.B, dtype=np.int64))
        self.traits[m] = r.uniform(0, 1, (n, 5))
        self.base_t[m] = r.uniform(12, 32, n)
        self.amp_t[m] = r.uniform(0, 4, n)
        self.offset_t[m] = 0
        self.hum[m] = r.uniform(20, 80, n)
        self.hour[m] = r.uniform(0, 24, n)
        self.noisy[m] = r.uniform(0, 0.35, n)
        self.has_orient[m] = r.random(n) < 0.5
        self.orient[m] = np.where(self.has_orient[m], 1, 0)
        self.owner[m] = r.random(n) < 0.3
        self.on_usb[m] = r.random(n) < 0.3
        self.battery[m] = np.where(self.on_usb[m], 1.0, r.uniform(0.2, 1.0, n))
        self.charging[m] = self.on_usb[m]
        self.st.reset(m, r)
        self.t[m] = 0

    def senses(self):
        r, B = self.rng, self.B
        h = self.hour
        day = ((h >= 8) & (h < 22)).astype(float)
        self.offset_t = self.offset_t * 0.995 + r.normal(0, 0.05, B) + (r.random(B) < 0.002) * r.normal(0, 4, B)
        temp = self.base_t + self.amp_t * np.sin(2 * np.pi * (h - 9) / 24) + self.offset_t
        sound = self.noisy * (day + 0.2 * (1 - day)) + np.abs(r.normal(0, 0.05, B))
        sound = np.where(r.random(B) < 0.01, r.uniform(0.7, 1.0, B), sound)
        # Orientation events (only for Pips that have a tilt sensor)
        upright = self.orient == 1
        ev = upright & (r.random(B) < 0.003)
        self.orient = np.where(ev, r.choice([2, 3], B), self.orient)
        back = (self.orient >= 2) & (r.random(B) < 0.05)
        self.orient = np.where(back, 1, self.orient)
        self.orient = np.where(self.has_orient == 1, self.orient, 0)
        # Owner comes and goes (more during the day)
        arrive = (self.owner == 0) & (r.random(B) < 0.01 * (0.2 + day))
        leave = (self.owner == 1) & (r.random(B) < 0.03)
        self.owner = np.where(arrive, 1, np.where(leave, 0, self.owner))
        called = self.last_action == CALL
        touched = (self.owner == 1) & (r.random(B) < 0.05 + 0.3 * called)
        # Battery
        start_charge = (~self.on_usb.astype(bool)) & (self.battery < 0.3) & (self.owner == 1) & \
                       (r.random(B) < 0.05 + 0.3 * called)
        self.charging = np.where(start_charge, 1, self.charging)
        self.battery = np.clip(self.battery + np.where(self.charging == 1, 0.02, -0.002), 0, 1)
        self.charging = np.where((self.battery >= 1.0) & (self.on_usb == 0), 0, self.charging)
        return {
            "temp": temp, "humidity": np.clip(self.hum + r.normal(0, 1, B), 0, 100), "hour": h.copy(),
            "sound": np.clip(sound, 0, 1), "battery": self.battery.copy(), "charging": self.charging.copy(),
            "touched": touched, "orient": self.orient.astype(np.int64).copy(),
        }

    def advance(self, a):
        self.last_action = a
        self.hour = (self.hour + STEP_HOURS) % 24
        self.t += 1
        done = self.t >= self.episode_steps
        self._new(done)
        return done
