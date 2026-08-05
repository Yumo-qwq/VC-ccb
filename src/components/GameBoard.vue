<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  goal: {
    type: Object,
    default: null
  },
  guesses: {
    type: Array,
    required: true
  },
  songs: {
    type: Array,
    required: true
  },
  status: {
    type: String,
    required: true
  },
  remaining: {
    type: Number,
    required: true
  },
  maxAttempts: {
    type: Number,
    required: true
  },
  notice: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['submit-guess', 'restart']);
const query = ref('');
const isSearchFocused = ref(false);

const usedIds = computed(() => new Set(props.guesses.map((guess) => guess.song.id)));
const suggestions = computed(() => {
  const normalized = query.value.trim().toLowerCase();
  return props.songs
    .filter((song) => !usedIds.value.has(song.id))
    .filter((song) => !normalized || song.searchText.includes(normalized))
    .slice(0, 10);
});
const showSuggestions = computed(() => {
  return props.status === 'playing' && isSearchFocused.value && suggestions.value.length > 0;
});

const progress = computed(() => {
  if (!props.maxAttempts) {
    return 0;
  }

  return Math.min(100, (props.guesses.length / props.maxAttempts) * 100);
});

const resultTitle = computed(() => {
  if (props.status === 'won') {
    return '猜中了';
  }

  if (props.status === 'lost') {
    return '次数用尽';
  }

  if (props.status === 'empty') {
    return '题池为空';
  }

  return '';
});

function submit() {
  emit('submit-guess', query.value);
}

function chooseSuggestion(song) {
  query.value = song.title;
  isSearchFocused.value = false;
}

watch(
  () => props.guesses.length,
  () => {
    query.value = '';
  }
);
</script>

<template>
  <section class="board-panel">
    <div class="board-top">
      <div>
        <p class="eyebrow">NOW PLAYING</p>
        <h2>猜出这首曲子</h2>
      </div>
      <div class="attempt-counter">
        <span>{{ remaining }}</span>
        <small>剩余</small>
      </div>
    </div>

    <form class="guess-form" @submit.prevent="submit">
      <label class="guess-box">
        <span>曲名</span>
        <div class="guess-input-wrap">
          <input
            v-model="query"
            type="search"
            autocomplete="off"
            placeholder="输入或选择曲名"
            :disabled="status !== 'playing'"
            @focus="isSearchFocused = true"
            @input="isSearchFocused = true"
            @blur="isSearchFocused = false"
          />
          <div v-if="showSuggestions" class="suggestion-menu" role="listbox">
            <button
              v-for="song in suggestions"
              :key="song.id"
              class="suggestion-option"
              type="button"
              role="option"
              @mousedown.prevent
              @click="chooseSuggestion(song)"
            >
              <strong>{{ song.title }}</strong>
              <small>{{ song.producer }} / {{ song.singers.join('、') }}</small>
            </button>
          </div>
        </div>
      </label>
      <button class="primary-button" type="submit" :disabled="status !== 'playing' || !query.trim()">
        猜测
      </button>
    </form>

    <p v-if="notice" class="notice">{{ notice }}</p>

    <div class="progress-track" aria-hidden="true">
      <span :style="{ width: `${progress}%` }"></span>
    </div>

    <div class="legend" aria-label="提示图例">
      <span><i class="legend-dot exact"></i>一致</span>
      <span><i class="legend-dot close"></i>接近</span>
      <span><i class="legend-arrow">↑↓</i>目标方向</span>
    </div>

    <div class="guess-table-wrap">
      <table class="guess-table">
        <thead>
          <tr>
            <th>曲名</th>
            <th>投稿年份</th>
            <th>引擎</th>
            <th>播放量</th>
            <th>UP主</th>
            <th>歌姬</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="guess in guesses" :key="guess.song.id">
            <td
              v-for="key in ['title', 'year', 'engine', 'plays', 'producer', 'singers']"
              :key="key"
              :class="['result-cell', guess.cells[key].state]"
              :title="guess.cells[key].hint"
            >
              {{ guess.cells[key].text }}
            </td>
          </tr>
          <tr v-if="!guesses.length">
            <td class="empty-state" colspan="6">
              从曲名开始。
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="status !== 'playing'" class="result-banner" :class="status">
      <div>
        <p class="eyebrow">RESULT</p>
        <h3>{{ resultTitle }}</h3>
        <p v-if="goal">
          答案是《{{ goal.title }}》 / {{ goal.year }} / {{ goal.producer }} / {{ goal.singers.join('、') }}
        </p>
        <p v-else>调整筛选条件后重新开始。</p>
      </div>
      <button class="primary-button" type="button" @click="emit('restart')">
        新一题
      </button>
    </div>
  </section>
</template>
