<script setup>
import { computed } from 'vue';

const props = defineProps({
  settings: {
    type: Object,
    required: true
  },
  producers: {
    type: Array,
    required: true
  },
  singers: {
    type: Array,
    required: true
  },
  engines: {
    type: Array,
    required: true
  },
  yearBounds: {
    type: Object,
    required: true
  },
  playBounds: {
    type: Object,
    required: true
  },
  poolSize: {
    type: Number,
    required: true
  }
});

const emit = defineEmits(['update-settings', 'restart']);

const modes = [
  {
    id: 'standard',
    name: '全曲库',
    note: '完整题池'
  },
  {
    id: 'producer',
    name: '单P主',
    note: '限定作者'
  },
  {
    id: 'era',
    name: '投稿年代',
    note: '限定年份'
  },
  {
    id: 'plays',
    name: '播放区间',
    note: '限定热度'
  },
  {
    id: 'custom',
    name: '自定义',
    note: '自由组合'
  }
];

const showProducer = computed(() => ['producer', 'custom'].includes(props.settings.mode));
const showYears = computed(() => ['era', 'custom'].includes(props.settings.mode));
const showPlays = computed(() => ['plays', 'custom'].includes(props.settings.mode));
const showVoiceFilters = computed(() => props.settings.mode === 'custom');

function patch(payload) {
  emit('update-settings', payload);
}

function selectMode(mode) {
  const payload = { mode };

  if (mode === 'custom') {
    payload.producer = '全部';
    payload.singer = '全部';
    payload.engine = '全部';
  }

  if (mode === 'producer' && props.settings.producer === '全部') {
    payload.producer = props.producers[0];
  }

  patch(payload);
}

function toNumber(event) {
  return Number(event.target.value);
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
</script>

<template>
  <aside class="mode-panel">
    <div class="panel-heading">
      <p class="eyebrow">PLAY MODE</p>
      <h2>玩法</h2>
    </div>

    <div class="mode-grid" role="list" aria-label="玩法选择">
      <button
        v-for="mode in modes"
        :key="mode.id"
        class="mode-option"
        :class="{ active: settings.mode === mode.id }"
        type="button"
        @click="selectMode(mode.id)"
      >
        <span>{{ mode.name }}</span>
        <small>{{ mode.note }}</small>
      </button>
    </div>

    <div class="control-stack">
      <label v-if="showProducer" class="field">
        <span>P主</span>
        <select
          :value="settings.producer"
          @change="patch({ producer: $event.target.value })"
        >
          <option v-if="settings.mode === 'custom'" value="全部">全部</option>
          <option v-for="producer in producers" :key="producer" :value="producer">
            {{ producer }}
          </option>
        </select>
      </label>

      <div v-if="showYears" class="paired-fields">
        <label class="field">
          <span>起始年份</span>
          <input
            type="number"
            :min="yearBounds.min"
            :max="yearBounds.max"
            :value="settings.fromYear"
            @input="patch({ fromYear: toNumber($event) })"
          />
        </label>
        <label class="field">
          <span>结束年份</span>
          <input
            type="number"
            :min="yearBounds.min"
            :max="yearBounds.max"
            :value="settings.toYear"
            @input="patch({ toYear: toNumber($event) })"
          />
        </label>
      </div>

      <div v-if="showPlays" class="paired-fields">
        <label class="field">
          <span>最低播放</span>
          <input
            type="number"
            :min="playBounds.min"
            :max="playBounds.max"
            step="100000"
            :value="settings.minPlays"
            @input="patch({ minPlays: toNumber($event) })"
          />
        </label>
        <label class="field">
          <span>最高播放</span>
          <input
            type="number"
            :min="playBounds.min"
            :max="playBounds.max"
            step="100000"
            :value="settings.maxPlays"
            @input="patch({ maxPlays: toNumber($event) })"
          />
        </label>
      </div>

      <div v-if="showPlays" class="range-note">
        {{ formatPlays(settings.minPlays) }} - {{ formatPlays(settings.maxPlays) }}
      </div>

      <label v-if="showVoiceFilters" class="field">
        <span>引擎</span>
        <select :value="settings.engine" @change="patch({ engine: $event.target.value })">
          <option value="全部">全部</option>
          <option v-for="engine in engines" :key="engine" :value="engine">
            {{ engine }}
          </option>
        </select>
      </label>

      <label v-if="showVoiceFilters" class="field">
        <span>歌姬</span>
        <select :value="settings.singer" @change="patch({ singer: $event.target.value })">
          <option value="全部">全部</option>
          <option v-for="singer in singers" :key="singer" :value="singer">
            {{ singer }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>猜测次数</span>
        <input
          type="number"
          min="3"
          max="20"
          :value="settings.maxAttempts"
          @input="patch({ maxAttempts: toNumber($event) })"
        />
      </label>
    </div>

    <footer class="panel-footer">
      <div>
        <span class="footer-label">当前题池</span>
        <strong>{{ poolSize }}</strong>
      </div>
      <button class="secondary-button" type="button" @click="emit('restart')">
        换一题
      </button>
    </footer>
  </aside>
</template>
