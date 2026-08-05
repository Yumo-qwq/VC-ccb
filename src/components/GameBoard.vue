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
const isResultModalDismissed = ref(false);

const usedIds = computed(() => new Set(props.guesses.map((guess) => guess.song.id)));
const cellLabels = {
  title: '曲名',
  year: '投稿年份',
  engine: '引擎',
  plays: '播放量',
  producer: 'UP主',
  singers: '歌姬'
};
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
    return '\u731c\u4e2d\u4e86';
  }

  if (props.status === 'lost') {
    return '\u6b21\u6570\u7528\u5c3d';
  }

  if (props.status === 'empty') {
    return '\u9898\u6c60\u4e3a\u7a7a';
  }

  return '';
});

const showResultModal = computed(() => {
  return !isResultModalDismissed.value && (props.status === 'won' || props.status === 'lost');
});

function submit() {
  emit('submit-guess', query.value);
}

function chooseSuggestion(song) {
  query.value = song.title;
  isSearchFocused.value = false;
}

function hideSuggestionsSoon() {
  window.setTimeout(() => {
    isSearchFocused.value = false;
  }, 120);
}

function formatPlays(value) {
  return new Intl.NumberFormat('zh-CN').format(value);
}

function closeResultModal() {
  isResultModalDismissed.value = true;
}

watch(
  () => props.guesses.length,
  () => {
    query.value = '';
  }
);

watch(
  () => props.status,
  () => {
    isResultModalDismissed.value = false;
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
            @blur="hideSuggestionsSoon"
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
              <span class="result-label">{{ cellLabels[key] }}</span>
              <span class="result-value">{{ guess.cells[key].text }}</span>
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

    <div v-if="status === 'empty'" class="result-banner empty">
      <div>
        <p class="eyebrow">RESULT</p>
        <h3>{{ resultTitle }}</h3>
        <p>调整筛选条件后重新开始。</p>
      </div>
      <button class="primary-button" type="button" @click="emit('restart')">
        重新开始
      </button>
    </div>

    <div
      v-if="showResultModal && goal"
      class="result-modal-backdrop"
      role="dialog"
      aria-modal="true"
      :aria-label="resultTitle"
      @click.self="closeResultModal"
    >
      <section class="result-modal">
        <div class="result-modal-head">
          <div>
            <p class="eyebrow">RESULT</p>
            <h3>{{ resultTitle }}</h3>
          </div>
          <button class="result-modal-close" type="button" aria-label="关闭结果弹窗" @click="closeResultModal">
            ×
          </button>
        </div>

        <div class="result-modal-body">
          <img class="result-modal-cover" :src="goal.cover" :alt="goal.title" />
          <div class="result-modal-info">
            <h4>{{ goal.title }}</h4>
            <dl class="result-meta-list">
              <div>
                <dt>P主</dt>
                <dd>{{ goal.producer }}</dd>
              </div>
              <div>
                <dt>歌姬</dt>
                <dd>{{ goal.singers.join('、') }}</dd>
              </div>
              <div>
                <dt>年份</dt>
                <dd>{{ goal.year }}</dd>
              </div>
              <div>
                <dt>引擎</dt>
                <dd>{{ goal.engine }}</dd>
              </div>
              <div>
                <dt>播放量</dt>
                <dd>{{ formatPlays(goal.plays) }}</dd>
              </div>
              <div>
                <dt>Bilibili</dt>
                <dd>
                  <a :href="goal.bilibiliUrl" target="_blank" rel="noreferrer noopener">打开链接</a>
                </dd>
              </div>
            </dl>
            <div class="result-modal-actions">
              <button class="primary-button" type="button" @click="emit('restart')">
                再来一局
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>
