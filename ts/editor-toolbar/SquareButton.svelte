<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="typescript">
    import type { Readable } from "svelte/store";
    import { getContext, onMount, createEventDispatcher } from "svelte";
    import { disabledKey, nightModeKey } from "./contextKeys";

    export let id: string;
    export let className = "";
    export let tooltip: string;

    export let onClick: (event: MouseEvent) => void;
    export let active = false;
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
        padding: 0;
    }

    @include button.btn-day;
    @include button.btn-night;

    span {
        display: inline-block;
        vertical-align: middle;

        /* constrain icon */
        width: calc(var(--toolbar-size) - 2px);
        height: calc(var(--toolbar-size) - 2px);

        & > :global(svg),
        & > :global(img) {
            fill: currentColor;
            vertical-align: unset;
            width: 100%;
            height: 100%;
        }
    }

    .dropdown-toggle::after {
        margin-right: 0.25rem;
    }
</style>

<button
    bind:this={buttonRef}
    {id}
    class={extendClassName(className)}
    class:active
    class:dropdown-toggle={dropdownToggle}
    class:btn-day={!nightMode}
    class:btn-night={nightMode}
    tabindex="-1"
    title={tooltip}
    disabled={_disabled}
    {...extraProps}
    on:click={onClick}
    on:mousedown|preventDefault>
    <span class="p-1"><slot /></span>
</button>
