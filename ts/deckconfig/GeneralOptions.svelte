<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import * as tr from "anki/i18n";
    import SpinBox from "./SpinBox.svelte";
    import CheckBox from "./CheckBox.svelte";
    import type { DeckConfigState } from "./lib";

    export let state: DeckConfigState;
    let config = state.currentConfig;
    let defaults = state.defaults;
</script>

<div>
    <h2>General</h2>

    <SpinBox
        label={tr.schedulingIgnoreAnswerTimesLongerThan()}
        subLabel="The maximum number of seconds to record for a single review."
        min={30}
        max={600}
        defaultValue={defaults.capAnswerTimeToSecs}
        bind:value={$config.capAnswerTimeToSecs} />

    <CheckBox
        label="Answer timer"
        subLabel={tr.schedulingShowAnswerTimer()}
        defaultValue={defaults.showTimer}
        bind:value={$config.showTimer} />

    <CheckBox
        label="Autoplay"
        subLabel="Don't play audio automatically"
        defaultValue={defaults.disableAutoplay}
        bind:value={$config.disableAutoplay} />

    <CheckBox
        label="Question Audio"
        subLabel={tr.schedulingAlwaysIncludeQuestionSideWhenReplaying()}
        defaultValue={defaults.skipQuestionWhenReplayingAnswer}
        bind:value={$config.skipQuestionWhenReplayingAnswer} />
</div>
