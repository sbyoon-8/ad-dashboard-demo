"""채널 x MMP(앱스플라이어) 성과 대시보드 (Streamlit)

폴더에 `YYYY-MM-DD_channel.csv`, `YYYY-MM-DD_appsflyer.csv` 파일을 넣으면
날짜별로 모두 읽어서 (일, 캠페인, 그룹, 소재) 키로 조인해 보여줍니다.
파일이 추가/변경되면 다음 새로고침 때 자동으로 반영됩니다.
"""
import io
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="채널 x MMP 성과 대시보드", layout="wide")

DEFAULT_DIR = str(Path(__file__).parent)
KEYS = ["일", "캠페인", "그룹", "소재"]
MMP_MAP = {"googleadwords_int": "구글", "Facebook Ads": "메타", "naver_search": "네이버"}


def files_signature(folder: str):
    """폴더 내 대상 파일의 (이름, 수정시각, 크기) 목록. 바뀌면 캐시가 갱신된다."""
    p = Path(folder)
    items = []
    for f in sorted(list(p.glob("*_channel.csv")) + list(p.glob("*_appsflyer.csv"))):
        s = f.stat()
        items.append((f.name, s.st_mtime_ns, s.st_size))
    return tuple(items)


def make_demo():
    """공개 데모용 가상 데이터 (실제 광고주 데이터가 아님). 고정 시드라 항상 같은 값이 나온다."""
    import random
    from datetime import date, timedelta

    rnd = random.Random(7)
    # (채널, 캠페인, 목적, 그룹들, 일 노출 범위, CTR 범위, CPC 범위, 회원가입률, 구매율, 객단가 범위)
    plan = [
        ("구글", "GGL_DEMO_01_신규가입", "신규가입", ["논타겟", "유사타겟"], (50000, 90000), (0.012, 0.022), (240, 340), 0.09, 0.028, (40000, 60000)),
        ("구글", "GGL_DEMO_02_리타겟팅", "리타겟팅", ["리마케팅"], (30000, 60000), (0.02, 0.035), (280, 380), 0.07, 0.05, (45000, 70000)),
        ("네이버", "NVR_DEMO_01_브랜드", "브랜드KW", ["논타겟"], (8000, 14000), (0.06, 0.10), (90, 140), 0.10, 0.08, (50000, 75000)),
        ("네이버", "NVR_DEMO_02_일반KW", "일반KW", ["논타겟", "유사타겟"], (20000, 40000), (0.02, 0.04), (350, 520), 0.06, 0.03, (40000, 60000)),
        ("메타", "META_DEMO_01_신규유저", "신규유저", ["유사타겟", "논타겟"], (80000, 140000), (0.008, 0.016), (180, 280), 0.06, 0.012, (35000, 55000)),
        ("메타", "META_DEMO_02_재구매", "재구매", ["윈백", "VIP"], (20000, 40000), (0.015, 0.03), (220, 320), 0.05, 0.035, (50000, 80000)),
    ]
    pool = [f"{t}_{k}_봄_{ab}_v1" for t in ("VID", "IMG", "TXT") for k in ("샘플혜택", "무료배송", "시즌특가") for ab in ("A", "B")]
    quality = {n: rnd.uniform(0.5, 1.7) for n in pool}
    src = {"구글": "googleadwords_int", "메타": "Facebook Ads", "네이버": "naver_search"}
    combos = [(p, g, c) for p in plan for g in p[3] for c in rnd.sample(pool, 3)]

    ch_rows, af_rows = [], []
    start = date(2025, 3, 3)
    for d in range(14):
        day = (start + timedelta(days=d)).isoformat()
        for (chn, camp, purpose, _g, imp_r, ctr_r, cpc_r, sr, pr, aov_r), grp, cre in combos:
            imp = rnd.randint(*imp_r) // 3
            clicks = int(imp * rnd.uniform(*ctr_r))
            cost = int(clicks * rnd.uniform(*cpc_r))
            signups = int(clicks * sr * rnd.uniform(0.8, 1.2))
            purch = int(clicks * pr * quality[cre] * rnd.uniform(0.7, 1.3))
            rev = int(purch * rnd.uniform(*aov_r))
            ch_rows.append({"일": day, "채널": chn, "채널분류": "외부", "캠페인": camp, "캠페인목적": purpose, "그룹": grp,
                            "소재": cre, "노출": imp, "클릭": clicks, "비용": cost, "회원가입": signups,
                            "구매": purch, "구매매출": rev})
            p_af = min(int(purch * rnd.uniform(0.65, 0.9)), purch)
            af_rows.append({"일": day, "미디어소스": src[chn], "캠페인": camp, "그룹": grp, "소재": cre,
                            "클릭": int(clicks * rnd.uniform(0.85, 0.97)), "회원가입": int(signups * rnd.uniform(0.7, 0.95)),
                            "구매": p_af, "구매매출": int(rev * (p_af / purch) * rnd.uniform(0.95, 1.05)) if purch else 0})
    return pd.DataFrame(ch_rows), pd.DataFrame(af_rows)


@st.cache_data(show_spinner=False)
def load(folder: str, signature, uploads=(), demo=False):
    p = Path(folder)

    def read_all(suffix):
        if uploads:  # 화면에서 업로드한 파일이 있으면 폴더 대신 사용
            frames = [pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
                      for name, data in sorted(uploads) if name.endswith(suffix)]
        else:
            frames = [pd.read_csv(f, encoding="utf-8-sig") for f in sorted(p.glob("*" + suffix))]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    ch, af = make_demo() if demo else (read_all("_channel.csv"), read_all("_appsflyer.csv"))
    if ch.empty:
        return ch, af, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    for d in (ch, af):
        if not d.empty:
            d["일"] = pd.to_datetime(d["일"]).dt.date

    af_cols = ["클릭", "회원가입", "구매", "구매매출"]
    if af.empty:
        joined = ch.copy()
        for c in af_cols:
            joined[f"{c}_MMP"] = pd.NA
        return ch, af, joined, pd.DataFrame(), pd.DataFrame()

    af_g = af.groupby(KEYS, as_index=False)[af_cols].sum().rename(columns={c: f"{c}_MMP" for c in af_cols})
    ch_g = ch.groupby(KEYS + ["채널", "채널분류", "캠페인목적"], as_index=False)[
        ["노출", "클릭", "비용", "회원가입", "구매", "구매매출"]
    ].sum()
    joined = ch_g.merge(af_g, on=KEYS, how="outer", indicator=True)
    only_ch = joined[joined["_merge"] == "left_only"][KEYS]
    only_af = joined[joined["_merge"] == "right_only"][KEYS]
    joined = joined[joined["_merge"] != "right_only"].drop(columns="_merge")
    return ch, af, joined, only_ch, only_af


def safe_div(a, b):
    return a / b if b else float("nan")


def won(x):
    return "-" if pd.isna(x) else f"{x:,.0f}원"


def pct(x):
    return "-" if pd.isna(x) else f"{x * 100:,.1f}%"


def summarize(df: pd.DataFrame, by):
    g = df.groupby(by, as_index=False)[
        ["노출", "클릭", "비용", "회원가입", "구매", "구매매출", "클릭_MMP", "회원가입_MMP", "구매_MMP", "구매매출_MMP"]
    ].sum(min_count=1)
    g["CTR"] = g["클릭"] / g["노출"]
    g["CPC"] = g["비용"] / g["클릭"]
    g["CPA(채널)"] = g["비용"] / g["구매"]
    g["ROAS(채널)"] = g["구매매출"] / g["비용"]
    g["ROAS(MMP)"] = g["구매매출_MMP"] / g["비용"]
    g["MMP/채널 구매"] = g["구매_MMP"] / g["구매"]
    return g


# ---------------------------------------------------------------- 사이드바
st.sidebar.header("데이터")
folder = st.sidebar.text_input("데이터 폴더", DEFAULT_DIR)
if st.sidebar.button("새로고침"):
    st.cache_data.clear()
st.sidebar.caption("폴더에 새 CSV가 추가되면 새로고침 시 자동 반영됩니다.")

uploaded = st.sidebar.file_uploader(
    "또는 CSV 직접 업로드", type="csv", accept_multiple_files=True,
    help="파일명이 `날짜_channel.csv`, `날짜_appsflyer.csv` 형식이어야 합니다. 업로드한 파일은 이 세션에서만 쓰이고 저장되지 않습니다.",
)
uploads = tuple((f.name, f.getvalue()) for f in uploaded or [])
demo = st.sidebar.checkbox(
    "가상 데모 데이터로 보기", value=st.query_params.get("demo") == "1",
    help="실제 광고주 데이터가 아닌, 임의로 만든 가상 데이터로 화면을 보여줍니다. 주소 뒤에 ?demo=1 을 붙이면 기본으로 켜집니다.",
)

if demo:
    sig = ("demo",)
elif uploads:
    sig = tuple((n, len(b)) for n, b in uploads)
elif Path(folder).is_dir():
    sig = files_signature(folder)
else:
    sig = ()

ch_raw, af_raw, joined, only_ch, only_af = load(folder, sig, uploads, demo)

if joined.empty:
    st.title("채널 x MMP 성과 대시보드")
    st.info("표시할 데이터가 없습니다. 왼쪽에서 `날짜_channel.csv`, `날짜_appsflyer.csv` 파일을 업로드하거나, "
            "데이터 폴더 경로를 확인해 주세요.")
    st.stop()

all_dates = sorted(joined["일"].unique())
d_min, d_max = all_dates[0], all_dates[-1]
if d_min == d_max:
    date_sel = (d_min, d_max)
    st.sidebar.caption(f"데이터 날짜: {d_min}")
else:
    date_sel = st.sidebar.date_input("기간", (d_min, d_max), min_value=d_min, max_value=d_max)
    if not isinstance(date_sel, tuple) or len(date_sel) != 2:
        st.stop()

channels = sorted(joined["채널"].unique())
ch_sel = st.sidebar.multiselect("채널", channels, default=channels)
purposes = sorted(joined["캠페인목적"].unique())
pur_sel = st.sidebar.multiselect("캠페인목적", purposes, default=purposes)

df = joined[
    (joined["일"] >= date_sel[0])
    & (joined["일"] <= date_sel[1])
    & (joined["채널"].isin(ch_sel))
    & (joined["캠페인목적"].isin(pur_sel))
]
if df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# ---------------------------------------------------------------- 본문
st.title("채널 x MMP 성과 대시보드")
st.caption(f"{date_sel[0]} ~ {date_sel[1]} · 채널 데이터와 앱스플라이어(MMP) 데이터를 일·캠페인·그룹·소재 키로 조인")

if demo:
    st.warning("⚠️ 가상 데모 데이터입니다. 실제 광고주 데이터가 아니며 수치는 임의로 만든 값입니다.")

tot = summarize(df.assign(_k="전체"), "_k").iloc[0]
c = st.columns(6)
c[0].metric("광고비", won(tot["비용"]))
c[1].metric("매출(채널)", won(tot["구매매출"]))
c[2].metric("매출(MMP)", won(tot["구매매출_MMP"]))
c[3].metric("ROAS(채널)", pct(tot["ROAS(채널)"]))
c[4].metric("ROAS(MMP)", pct(tot["ROAS(MMP)"]))
c[5].metric("MMP/채널 구매 비율", pct(tot["MMP/채널 구매"]))

c = st.columns(6)
c[0].metric("노출", f"{tot['노출']:,.0f}")
c[1].metric("클릭", f"{tot['클릭']:,.0f}")
c[2].metric("CPC", won(tot["CPC"]))
c[3].metric("구매(채널)", f"{tot['구매']:,.0f}")
c[4].metric("구매(MMP)", f"{tot['구매_MMP']:,.0f}" if pd.notna(tot["구매_MMP"]) else "-")
c[5].metric("CPA(채널)", won(tot["CPA(채널)"]))

st.divider()
tab1, tab2, tab3, tab_rank, tab4 = st.tabs(["일별 추이", "채널별", "캠페인·소재", "소재 순위", "데이터 점검"])

# ---- 일별 추이
with tab1:
    daily = summarize(df, "일").sort_values("일")
    if len(daily) < 2:
        st.info("일별 추이 차트는 2일 이상의 데이터가 쌓이면 표시됩니다. (현재 1일)")
    else:
        fig = go.Figure()
        fig.add_bar(x=daily["일"], y=daily["비용"], name="광고비", yaxis="y", opacity=0.5)
        fig.add_scatter(x=daily["일"], y=daily["ROAS(채널)"] * 100, name="ROAS(채널) %", yaxis="y2", mode="lines+markers")
        fig.add_scatter(x=daily["일"], y=daily["ROAS(MMP)"] * 100, name="ROAS(MMP) %", yaxis="y2", mode="lines+markers")
        fig.update_layout(
            yaxis=dict(title="광고비(원)"),
            yaxis2=dict(title="ROAS(%)", overlaying="y", side="right"),
            legend=dict(orientation="h", y=1.12),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig, width="stretch")
    show = daily[["일", "비용", "구매매출", "구매매출_MMP", "ROAS(채널)", "ROAS(MMP)", "MMP/채널 구매"]]
    st.dataframe(
        show,
        hide_index=True,
        width="stretch",
        column_config={
            "ROAS(채널)": st.column_config.NumberColumn(format="percent"),
            "ROAS(MMP)": st.column_config.NumberColumn(format="percent"),
            "MMP/채널 구매": st.column_config.NumberColumn(format="percent"),
            "비용": st.column_config.NumberColumn(format="%d"),
            "구매매출": st.column_config.NumberColumn(format="%d"),
            "구매매출_MMP": st.column_config.NumberColumn(format="%d"),
        },
    )

# ---- 채널별
with tab2:
    by_ch = summarize(df, ["채널", "채널분류"]).sort_values("비용", ascending=False)
    left, right = st.columns(2)
    with left:
        f = go.Figure()
        f.add_bar(x=by_ch["채널"], y=by_ch["ROAS(채널)"] * 100, name="채널 기준")
        f.add_bar(x=by_ch["채널"], y=by_ch["ROAS(MMP)"] * 100, name="MMP 기준")
        f.update_layout(title="채널별 ROAS(%)", barmode="group", margin=dict(t=50, b=20))
        st.plotly_chart(f, width="stretch")
    with right:
        f = go.Figure(go.Pie(labels=by_ch["채널"], values=by_ch["비용"], hole=0.5))
        f.update_layout(title="광고비 비중", margin=dict(t=50, b=20))
        st.plotly_chart(f, width="stretch")
    st.dataframe(
        by_ch[["채널", "채널분류", "비용", "노출", "클릭", "CTR", "CPC", "구매", "구매_MMP", "MMP/채널 구매",
               "구매매출", "구매매출_MMP", "ROAS(채널)", "ROAS(MMP)", "CPA(채널)"]],
        hide_index=True,
        width="stretch",
        column_config={
            "CTR": st.column_config.NumberColumn(format="percent"),
            "MMP/채널 구매": st.column_config.NumberColumn(format="percent"),
            "ROAS(채널)": st.column_config.NumberColumn(format="percent"),
            "ROAS(MMP)": st.column_config.NumberColumn(format="percent"),
            "CPC": st.column_config.NumberColumn(format="%d"),
            "CPA(채널)": st.column_config.NumberColumn(format="%d"),
            "비용": st.column_config.NumberColumn(format="%d"),
            "구매매출": st.column_config.NumberColumn(format="%d"),
            "구매매출_MMP": st.column_config.NumberColumn(format="%d"),
            "노출": st.column_config.NumberColumn(format="%d"),
            "클릭": st.column_config.NumberColumn(format="%d"),
        },
    )

# ---- 캠페인·소재
with tab3:
    level = st.radio("집계 단위", ["캠페인", "캠페인 > 그룹", "캠페인 > 그룹 > 소재"], horizontal=True)
    by = {"캠페인": ["채널", "캠페인", "캠페인목적"],
          "캠페인 > 그룹": ["채널", "캠페인", "캠페인목적", "그룹"],
          "캠페인 > 그룹 > 소재": ["채널", "캠페인", "캠페인목적", "그룹", "소재"]}[level]
    t = summarize(df, by)
    sort_col = st.selectbox("정렬 기준", ["비용", "구매매출", "ROAS(채널)", "ROAS(MMP)", "CPA(채널)", "MMP/채널 구매"])
    t = t.sort_values(sort_col, ascending=False)
    st.dataframe(
        t[by + ["비용", "클릭", "구매", "구매_MMP", "MMP/채널 구매", "구매매출", "구매매출_MMP", "ROAS(채널)", "ROAS(MMP)", "CPA(채널)"]],
        hide_index=True,
        width="stretch",
        column_config={
            "MMP/채널 구매": st.column_config.NumberColumn(format="percent"),
            "ROAS(채널)": st.column_config.NumberColumn(format="percent"),
            "ROAS(MMP)": st.column_config.NumberColumn(format="percent"),
            "CPA(채널)": st.column_config.NumberColumn(format="%d"),
            "비용": st.column_config.NumberColumn(format="%d"),
            "구매매출": st.column_config.NumberColumn(format="%d"),
            "구매매출_MMP": st.column_config.NumberColumn(format="%d"),
        },
    )
    st.download_button("현재 표 CSV 다운로드", t.to_csv(index=False).encode("utf-8-sig"), "campaign_summary.csv", "text/csv")

# ---- 소재 순위
with tab_rank:
    st.caption("소재(채널·캠페인·그룹 단위)를 ROAS 기준으로 줄 세워 고효율/저효율 소재를 봅니다. 광고비가 너무 적은 소재는 우연의 영향이 커서 최소 광고비로 걸러낼 수 있습니다.")
    r1, r2, r3 = st.columns(3)
    basis = r1.radio("효율 기준", ["ROAS(채널)", "ROAS(MMP)"], horizontal=True)
    min_cost = r2.number_input("최소 광고비(원)", min_value=0, value=0, step=10000,
                               help="이 금액보다 광고비가 적은 소재는 순위에서 제외합니다.")
    n_max = 20
    top_n = r3.slider("표시 개수(상위/하위 각각)", 3, n_max, 5)

    cr = summarize(df, ["채널", "캠페인", "그룹", "소재"])
    cr["소재(캠페인/그룹)"] = cr["소재"] + "  (" + cr["캠페인"] + " / " + cr["그룹"] + ")"
    cr = cr[(cr["비용"] >= min_cost)].dropna(subset=[basis])
    cr = cr.sort_values(basis, ascending=False).reset_index(drop=True)
    cr.insert(0, "순위", cr.index + 1)

    if len(cr) == 0:
        st.warning("조건에 맞는 소재가 없습니다. 최소 광고비를 낮춰 보세요.")
    else:
        avg_roas = tot[basis]
        st.write(f"순위 대상 소재 **{len(cr)}개** · 전체 평균 {basis} **{pct(avg_roas)}**")
        n = min(top_n, len(cr) // 2) if len(cr) >= 2 else len(cr)
        n = max(n, 1)
        top, bottom = cr.head(n), cr.tail(n).sort_values(basis)

        show_cols = ["순위", "채널", "소재", "캠페인", "그룹", "비용", "구매", "구매_MMP", "구매매출", "구매매출_MMP",
                     "ROAS(채널)", "ROAS(MMP)", "CPA(채널)"]
        cfg = {
            "ROAS(채널)": st.column_config.NumberColumn(format="percent"),
            "ROAS(MMP)": st.column_config.NumberColumn(format="percent"),
            "CPA(채널)": st.column_config.NumberColumn(format="%d"),
            "비용": st.column_config.NumberColumn(format="%d"),
            "구매매출": st.column_config.NumberColumn(format="%d"),
            "구매매출_MMP": st.column_config.NumberColumn(format="%d"),
        }

        def bar(d, title, color):
            d = d.sort_values(basis, ascending=True)
            f = go.Figure(go.Bar(x=d[basis] * 100, y=d["소재(캠페인/그룹)"], orientation="h", marker_color=color,
                                 text=[f"{v * 100:,.0f}%" for v in d[basis]], textposition="auto"))
            f.add_vline(x=avg_roas * 100, line_dash="dash", annotation_text="평균", annotation_position="top")
            f.update_layout(title=title, xaxis_title=f"{basis} (%)", yaxis_title=None, margin=dict(t=50, b=20, l=10),
                            height=max(260, 55 * len(d) + 120))
            return f

        left, right = st.columns(2)
        with left:
            st.plotly_chart(bar(top, f"고효율 TOP {n}", "#2f5bff"), width="stretch")
        with right:
            st.plotly_chart(bar(bottom, f"저효율 BOTTOM {n}", "#e5484d"), width="stretch")

        st.subheader(f"고효율 TOP {n}")
        st.dataframe(top[show_cols], hide_index=True, width="stretch", column_config=cfg)
        st.subheader(f"저효율 BOTTOM {n}")
        st.dataframe(bottom[show_cols], hide_index=True, width="stretch", column_config=cfg)
        with st.expander("전체 소재 순위 보기"):
            st.dataframe(cr[show_cols], hide_index=True, width="stretch", column_config=cfg)
        st.download_button("전체 순위 CSV 다운로드", cr[show_cols].to_csv(index=False).encode("utf-8-sig"),
                           "creative_ranking.csv", "text/csv")

# ---- 데이터 점검
with tab4:
    st.subheader("로드된 파일")
    st.write(f"- 채널 파일 {sum(1 for s in sig if s[0].endswith('_channel.csv'))}개 / "
             f"MMP 파일 {sum(1 for s in sig if s[0].endswith('_appsflyer.csv'))}개")
    st.write(f"- 데이터 날짜: {d_min} ~ {d_max} ({len(all_dates)}일)")
    ch_days = set(ch_raw["일"]) if not ch_raw.empty else set()
    af_days = set(af_raw["일"]) if not af_raw.empty else set()
    miss_af, miss_ch = sorted(ch_days - af_days), sorted(af_days - ch_days)
    if miss_af:
        st.warning(f"MMP 데이터가 없는 날짜: {', '.join(map(str, miss_af))}")
    if miss_ch:
        st.warning(f"채널 데이터가 없는 날짜: {', '.join(map(str, miss_ch))}")
    st.subheader("조인 점검")
    if len(only_ch):
        st.warning(f"채널에만 있는 행 {len(only_ch)}건 (MMP 매칭 실패)")
        st.dataframe(only_ch, hide_index=True)
    else:
        st.success("채널 데이터의 모든 행이 MMP와 매칭됐습니다.")
    if len(only_af):
        st.warning(f"MMP에만 있는 행 {len(only_af)}건 (채널 매칭 실패)")
        st.dataframe(only_af, hide_index=True)
    else:
        st.success("MMP 데이터의 모든 행이 채널과 매칭됐습니다.")
    if not af_raw.empty:
        mapped = af_raw["미디어소스"].map(MMP_MAP)
        unknown = sorted(af_raw.loc[mapped.isna(), "미디어소스"].unique())
        if unknown:
            st.warning(f"매핑되지 않은 미디어소스: {', '.join(unknown)}")
    with st.expander("조인된 원본 데이터 보기"):
        st.dataframe(df, hide_index=True, width="stretch")
