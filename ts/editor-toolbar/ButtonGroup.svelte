<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="typescript">
    import type { ToolbarItem } from "./types";
    import { getContext } from "svelte";
    import { nightModeKey } from "./contextKeys";

    export let id: string | undefined = undefined;
    export let className = "";
    export let buttons: ToolbarItem[];

    function filterHidden({ hidden = false, ...props }) {
        return props;
    }

    const nightMode = getContext(nightModeKey);
</script>

<style lang="scss">
    ul {
        display: flex;
        justify-items: start;

        flex-wrap: var(--toolbar-wrap);
        overflow-y: auto;

        padding-inline-start: 0;
        margin: 0 0 calc(var(--toolbar-size) / 10);
    }

    .border-overlap-group {
        :global(button),
        :global(select) {
            margin-left: -1px;
        }
    }

    li {
        display: inline-block;

        > :global(button),
        > :global(select) {
            border-radius: 0;
        }

        &:nth-child(1) {
            margin-left: calc(var(--toolbar-size) / 7.5);

            > :global(button),
            > :global(select) {
                /* default 0.25rem */
                border-top-left-radius: calc(var(--toolbar-size) / 7.5);
                border-bottom-left-radius: calc(var(--toolbar-size) / 7.5);
            }
        }

        &:nth-last-child(1) {
            margin-right: calc(var(--toolbar-size) / 7.5);

            > :global(button),
            > :global(select) {
                border-top-right-radius: calc(var(--toolbar-size) / 7.5);
                border-bottom-right-radius: calc(var(--toolbar-size) / 7.5);
            }
        }

        &.gap-item:not(:nth-child(1)) {
            margin-left: 1px;
        }
    }
</style>

<ul {id} class={className} class:border-overlap-group={!nightMode}>
    {#each buttons as button}
        {#if !button.hidden}
            <li class:gap-item={nightMode}>
                <svelte:component this={button.component} {...filterHidden(button)} />
            </li>
        {/if}
    {/each}
</ul>
