<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import ConfigEntry from "./ConfigEntry.svelte";

    export let label: string;
    export let subLabel: string;
    export let choices: string[];
    export let value: number = 0;
    export let defaultValue: number;
</script>

<ConfigEntry {label} {subLabel} bind:value {defaultValue}>
    <select bind:value class="form-select">
        {#each choices as choice, idx}
            <option value={idx}>{choice}</option>
        {/each}
    </select>
</ConfigEntry>
