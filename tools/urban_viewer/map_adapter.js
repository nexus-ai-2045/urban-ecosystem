/**
 * map_adapter.js — adapter 共通インターフェース定義 (抽象基底クラス)。
 *
 * 正本: docs/ai-ecosystem-tool-spec.md §5.1.5 / §11
 * 契約: init / setLayer / upsertAgents / highlight / onAgentClick
 *
 * app.js は GOOGLE_MAPS_API_KEY の有無でアダプタを差し替える。
 * 両アダプタはこのインターフェースを実装する。
 *
 * 識別子は英語 / コメントは日本語。
 */

"use strict";

/**
 * MapAdapter 抽象基底クラス。
 * 派生クラスは全メソッドを実装しなければならない。
 */
export class MapAdapter {
    /**
     * 地図 / canvas を初期化する。
     * @param {Object} [options]
     * @returns {Promise<void>|void}
     */
    // eslint-disable-next-line no-unused-vars
    init(options = {}) {
        throw new Error("MapAdapter.init() は派生クラスで実装する");
    }

    /**
     * GeoJSON レイヤーの表示/非表示とデータを設定する。
     * @param {"poi"|"aoi"|"road"|"agent"} name
     * @param {boolean} visible
     * @param {Object|null} [geojson]
     */
    // eslint-disable-next-line no-unused-vars
    setLayer(name, visible, geojson = null) {
        throw new Error("MapAdapter.setLayer() は派生クラスで実装する");
    }

    /**
     * エージェントマーカーを一括更新する。
     * @param {Array<{id:number, lat:number, lon:number}>} agents
     * @returns {Promise<void>|void}
     */
    // eslint-disable-next-line no-unused-vars
    upsertAgents(agents) {
        throw new Error("MapAdapter.upsertAgents() は派生クラスで実装する");
    }

    /**
     * 指定 agentId を強調表示する (null で解除)。
     * @param {number|null} agentId
     */
    // eslint-disable-next-line no-unused-vars
    highlight(agentId) {
        throw new Error("MapAdapter.highlight() は派生クラスで実装する");
    }

    /**
     * エージェントクリック時のコールバックを登録する。
     * @param {(agentId: number) => void} cb
     */
    // eslint-disable-next-line no-unused-vars
    onAgentClick(cb) {
        throw new Error("MapAdapter.onAgentClick() は派生クラスで実装する");
    }

    /**
     * 選択中 agent から友達 agent への社会的リンク線を描画する。
     * @param {{ id:number, lat:number, lon:number }} centerAgent - 選択中 agent の現在位置
     * @param {Array<{ id:number, lat:number, lon:number }>} friendAgents - 友達の現在位置リスト
     */
    // eslint-disable-next-line no-unused-vars
    drawSocialLinks(centerAgent, friendAgents) {
        throw new Error("MapAdapter.drawSocialLinks() は派生クラスで実装する");
    }

    /**
     * drawSocialLinks で描画した社会的リンク線をすべて消去する。
     */
    clearSocialLinks() {
        throw new Error("MapAdapter.clearSocialLinks() は派生クラスで実装する");
    }
}
