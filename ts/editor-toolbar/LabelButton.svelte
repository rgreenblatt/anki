<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="typescript">
    import type { Readable } from "svelte/store";
    import { onMount, createEventDispatcher, getContext } from "svelte";
    import { disabledKey, nightModeKey } from "./contextKeys";

    export let id: string;
    export let className = "";

    export let label: string;
    export let tooltip: string;
    export let onClick: (event: MouseEvent) => void;
    export let disables = true;
    export let dropdownToggle = false;

    $: extraProps = dropdownToggle
        ? {
              "data-bs-toggle": "dropdown",
              "aria-expanded": "false",
          }
        : {};

    let buttonRef: HTMLButtonElement;

    function extendClassName(className: string): string {
        return `btn ${className}`;
    }

    const disabled = getContext<Readable<boolean>>(disabledKey);
    $: _disabled = disables && $disabled;

    const nightMode = getContext<boolean>(nightModeKey);

    const dispatch = createEventDispatcher();
    onMount(() => dispatch("mount", { button: buttonRef }));
</script>

<style lang="scss">
    @use "ts/sass/button_mixins" as button;

    button {
        padding: 0 calc(var(--toolbar-size) / 3);
        font-size: calc(var(--toolbar-size) / 2.3);
        width: auto;
        height: var(--toolbar-size);
    }

    @include button.btn-day;
    @include button.btn-night;
</style>

<button
    bind:this={buttonRef}
    {id}
    class={extendClassName(className)}
    class:dropdown-toggle={dropdownToggle}
    class:btn-day={!nightMode}
    class:btn-night={nightMode}
    tabindex="-1"
    disabled={_disabled}
    title={tooltip}
    {...extraProps}
    on:click={onClick}
    on:mousedown|preventDefault>
    {label}
</button>
