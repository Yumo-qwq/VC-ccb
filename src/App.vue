<script setup>
import { computed, reactive, ref, watch } from 'vue';
import GameBoard from './components/GameBoard.vue';
import GameModePanel from './components/GameModePanel.vue';
import rawSongs from './data/vcpedia_legendary_songs.json';

const songs = rawSongs.filter((song) => Number.isFinite(song.plays)).map((song) => ({
  ...song,
  searchKeys: [song.title, ...(song.aliases || [])].map((value) => value.toLowerCase()),
  searchText: [song.title, ...(song.aliases || [])].join(' ').toLowerCase()
}));

const producers = unique(songs.map((song) => song.producer));
const singers = unique(songs.flatMap((song) => song.singers));
const engines = unique(songs.map((song) => song.engine));
const yearBounds = {
  min: Math.min(...songs.map((song) => song.year)),
  max: Math.max(...songs.map((song) => song.year))
};
const playBounds = {
  min: 0,
  max: Math.max(...songs.map((song) => song.plays))
};

const settings = reactive({
  mode: 'standard',
  producer: 'ilem',
  singer: '全部',
  engine: '全部',
  fromYear: yearBounds.min,
  toYear: yearBounds.max,
  minPlays: 0,
  maxPlays: playBounds.max,
  maxAttempts: 10
});

const goal = ref(null);
const guesses = ref([]);
const status = ref('playing');
const notice = ref('');
const screen = ref('home');

const currentPool = computed(() => {
  return songs.filter((song) => {
    if (settings.mode === 'producer' && song.producer !== settings.producer) {
      return false;
    }

    if (settings.mode === 'era' && !isBetween(song.year, settings.fromYear, settings.toYear)) {
      return false;
    }

    if (settings.mode === 'plays' && !isBetween(song.plays, settings.minPlays, settings.maxPlays)) {
      return false;
    }

    if (settings.mode === 'custom') {
      const matchesProducer =
        settings.producer === '全部' || song.producer === settings.producer;
      const matchesSinger =
        settings.singer === '全部' || song.singers.includes(settings.singer);
      const matchesEngine =
        settings.engine === '全部' || song.engine === settings.engine;

      return (
        matchesProducer &&
        matchesSinger &&
        matchesEngine &&
        isBetween(song.year, settings.fromYear, settings.toYear) &&
        isBetween(song.plays, settings.minPlays, settings.maxPlays)
      );
    }

    return true;
  });
});

const remaining = computed(() => {
  return Math.max(0, Number(settings.maxAttempts) - guesses.value.length);
});

const poolKey = computed(() => {
  return [
    settings.mode,
    settings.producer,
    settings.singer,
    settings.engine,
    settings.fromYear,
    settings.toYear,
    settings.minPlays,
    settings.maxPlays
  ].join('|');
});

function patchSettings(payload) {
  Object.assign(settings, payload);
}

function beginGame() {
  startRound();
  screen.value = 'game';
}

function startRound() {
  guesses.value = [];
  notice.value = '';

  const pool = currentPool.value;
  if (!pool.length) {
    goal.value = null;
    status.value = 'empty';
    return;
  }

  goal.value = pool[Math.floor(Math.random() * pool.length)];
  status.value = 'playing';
}

function submitGuess(query) {
  if (status.value !== 'playing') {
    return;
  }

  const normalized = query.trim().toLowerCase();
  const song = currentPool.value.find((item) => {
    return item.searchKeys.includes(normalized);
  });

  if (!song) {
    notice.value = '请从当前玩法题库中选择一个曲名。';
    return;
  }

  if (guesses.value.some((guess) => guess.song.id === song.id)) {
    notice.value = '这首已经猜过了。';
    return;
  }

  const row = buildGuessRow(song, goal.value);
  guesses.value = [row, ...guesses.value];
  notice.value = '';

  if (song.id === goal.value.id) {
    status.value = 'won';
    return;
  }

  if (guesses.value.length >= Number(settings.maxAttempts)) {
    status.value = 'lost';
  }
}

function buildGuessRow(song, target) {
  return {
    song,
    cells: {
      title: compareTitle(song, target),
      year: compareNumber(song.year, target.year, 2, String(song.year)),
      engine: compareText(song.engine, target.engine),
      plays: compareNumber(song.plays, target.plays, Math.max(1200000, target.plays * 0.25), formatPlays(song.plays)),
      producer: compareText(song.producer, target.producer),
      singers: compareSingers(song.singers, target.singers)
    }
  };
}

function compareTitle(song, target) {
  return {
    text: song.title,
    state: song.id === target.id ? 'exact' : 'miss',
    hint: song.id === target.id ? '猜中' : '曲名不同'
  };
}

function compareText(value, target) {
  return {
    text: value,
    state: value === target ? 'exact' : 'miss',
    hint: value === target ? '完全一致' : '不同'
  };
}

function compareSingers(value, target) {
  const exact = value.length === target.length && value.every((item) => target.includes(item));
  const overlap = value.some((item) => target.includes(item));

  return {
    text: value.join(' / '),
    state: exact ? 'exact' : overlap ? 'close' : 'miss',
    hint: exact ? '歌姬完全一致' : overlap ? '有相同歌姬' : '歌姬不同'
  };
}

function compareNumber(value, target, closeRange, display) {
  const diff = target - value;
  const exact = diff === 0;
  const close = Math.abs(diff) <= closeRange;

  return {
    text: exact ? display : `${display} ${diff > 0 ? '↑' : '↓'}`,
    state: exact ? 'exact' : close ? 'close' : 'miss',
    hint: exact ? '完全一致' : diff > 0 ? '目标更高' : '目标更低'
  };
}

function formatPlays(value) {
  if (value >= 100000000) {
    return `${(value / 100000000).toFixed(1)}亿`;
  }

  if (value >= 10000) {
    return `${Math.round(value / 10000)}万`;
  }

  return String(value);
}

function isBetween(value, min, max) {
  const low = Math.min(Number(min), Number(max));
  const high = Math.max(Number(min), Number(max));
  return value >= low && value <= high;
}

function unique(values) {
  return Array.from(new Set(values)).sort((a, b) => String(a).localeCompare(String(b), 'zh-Hans-CN'));
}

watch(poolKey, startRound);
watch(
  () => settings.maxAttempts,
  () => {
    if (guesses.value.length >= Number(settings.maxAttempts) && status.value === 'playing') {
      status.value = 'lost';
    }
  }
);

startRound();
</script>

<template>
  <main class="app-shell">
    <section v-if="screen === 'home'" class="home-screen" aria-label="游戏入口">
      <h1>中V名曲猜猜呗</h1>
      <div class="home-actions">
        <button class="primary-button home-button" type="button" @click="beginGame">
          开始猜歌
        </button>
        <button class="secondary-button home-button" type="button" @click="screen = 'settings'">
          设置
        </button>
      </div>
    </section>

    <section v-else-if="screen === 'settings'" class="settings-screen" aria-label="设置">
      <div class="screen-actions">
        <button class="secondary-button" type="button" @click="screen = 'home'">
          返回
        </button>
        <button class="primary-button" type="button" @click="beginGame">
          开始猜歌
        </button>
      </div>
      <GameModePanel
        :settings="settings"
        :producers="producers"
        :singers="singers"
        :engines="engines"
        :year-bounds="yearBounds"
        :play-bounds="playBounds"
        :pool-size="currentPool.length"
        @update-settings="patchSettings"
        @restart="startRound"
      />
    </section>

    <section v-else class="game-screen" aria-label="猜歌">
      <div class="screen-actions">
        <button class="secondary-button" type="button" @click="screen = 'home'">
          返回首页
        </button>
        <button class="secondary-button" type="button" @click="screen = 'settings'">
          设置
        </button>
      </div>
      <GameBoard
        :goal="goal"
        :guesses="guesses"
        :songs="currentPool"
        :status="status"
        :remaining="remaining"
        :max-attempts="Number(settings.maxAttempts)"
        :notice="notice"
        @submit-guess="submitGuess"
        @restart="startRound"
      />
    </section>
  </main>
</template>
