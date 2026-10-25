"""Session-scoped team data exploration and reproducible analysis exports."""
import io
import json
from datetime import datetime, timezone
import pandas as pd
import plotly.express as px
import streamlit as st

SOURCES = {
    'NCS 272개 직무 마스터 (추출)': '../processed/ncs_272_jobs.csv',
    'NCS 1,360개 능력단위 (추출)': '../processed/ncs_1360_units.csv',
    'NCS KSA 지식·기술·태도 마스터 (추출)': '../processed/ncs_ksa_master.csv',
    'KOSIS 직종별 노동력 부족 통계': 'occupation_labor_shortage.csv',
    '강좌 통합 샘플': 'kmooc_courses.csv',
    'NCS 교육과정 샘플': 'ncs_curriculums.csv',
    '원격훈련 통계 샘플': 'remote_learning_stats.csv',
}

def parse_csv(payload, encoding):
    frame = pd.read_csv(io.BytesIO(payload), encoding=encoding, dtype=str)
    if len(frame.columns) == 0:
        raise ValueError('열 이름이 없습니다.')
    return frame

def quality_table(frame):
    missing = frame.isna() | frame.fillna('').astype(str).apply(lambda s: s.str.strip().eq(''))
    return pd.DataFrame({'항목':frame.columns, '결측 건수':missing.sum().values,
        '결측률 (%)':(missing.mean().fillna(0)*100).round(1).values,
        '고유값 수':frame.nunique().values})

def summarize(frame, group, metric, operation):
    work = frame.copy()
    work[group] = work[group].fillna('미확인').replace(r'^\s*$', '미확인', regex=True)
    if operation == '건수':
        return work.groupby(group, dropna=False).size().reset_index(name='건수'), 0
    numeric = pd.to_numeric(work[metric], errors='coerce').replace([float('inf'),float('-inf')], float('nan'))
    excluded = int(numeric.isna().sum())
    work['_measure'] = numeric
    work = work[numeric.notna()]
    funcs = {'평균':'mean','중앙값':'median','합계':'sum'}
    result = work.groupby(group)['_measure'].agg(['count', funcs[operation]]).reset_index()
    result.columns = [group,'유효 관측 수',f'{metric} · {operation}']
    return result, excluded

def csv_button(frame, label, name):
    st.download_button(label, frame.to_csv(index=False).encode('utf-8-sig'), name, 'text/csv')

def workspace(root):
    st.title('팀 자료실·분석실')
    st.write('자료를 선택하고 품질을 확인한 뒤, 같은 조건으로 비교·분석하세요. 분석 조건과 해석을 내려받아 팀원에게 전달할 수 있습니다.')
    a,b = st.columns([2,1])
    choice = a.selectbox('분석 자료', list(SOURCES) + ['CSV 업로드'])
    frame = None
    source = ''
    if choice == 'CSV 업로드':
        encoding = b.selectbox('파일 인코딩', ['utf-8-sig','cp949','euc-kr'])
        upload = st.file_uploader('팀 분석용 CSV (최대 20MB)', type=['csv'])
        st.caption('업로드는 현재 접속 세션에서만 사용합니다. 다른 팀원의 화면이나 공용 저장소에 자동으로 저장되지 않습니다.')
        if upload is None:
            st.info('첫 행에 열 이름이 있는 CSV를 선택하세요. 직무코드의 앞자리 0을 보존하여 불러옵니다.')
            return
        if upload.size > 20 * 1024 * 1024:
            st.error('20MB 이하의 CSV로 나누어 올려주세요.')
            return
        try:
            frame = parse_csv(upload.getvalue(), encoding)
        except (UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError, ValueError):
            st.error('CSV를 읽을 수 없습니다. 인코딩과 쉼표 구분, 첫 행의 열 이름을 확인하세요.')
            return
        source = upload.name
        st.info('사용자 업로드 자료입니다. 실제 수집 여부와 정확성은 별도로 확인해야 합니다.')
    else:
        source = SOURCES[choice]
        frame = pd.read_csv(root / 'data/sample' / source, dtype=str)
        st.warning('저장소에 포함된 시연용 샘플입니다. 공식 통계나 실제 모집 자료가 아닙니다.')
    context = st.text_input('자료 출처·기준 기간', placeholder='예: 서울 열린데이터광장 / 2026년 8월 / 수집 담당자')
    a,b,c = st.columns(3)
    a.metric('원자료 행 수', f'{len(frame):,}')
    b.metric('항목 수', len(frame.columns))
    c.metric('전체 행 중복 수', int(frame.duplicated().sum()))
    st.caption('중복은 모든 항목이 같은 행 기준입니다. 자동으로 삭제하지 않습니다.')
    raw, quality, analysis, notes = st.tabs(['원자료 탐색','데이터 품질','비교 분석','분석 기록·공유'])
    with raw:
        a,b = st.columns(2)
        field = a.selectbox('검색할 항목', frame.columns)
        query = b.text_input('포함할 검색어', placeholder='비워두면 전체 자료')
        selected = frame[frame[field].fillna('').str.contains(query,regex=False,case=False)] if query else frame.copy()
        filter_col = st.selectbox('범주 필터', ['사용 안 함'] + list(frame.columns))
        values = []
        if filter_col != '사용 안 함':
            options = sorted(selected[filter_col].dropna().unique())
            values = st.multiselect('포함할 값 (비우면 전체)',options)
            if values: selected = selected[selected[filter_col].isin(values)]
        st.write(f'필터 결과: {len(selected):,}행')
        st.dataframe(selected.head(1000),width="stretch",hide_index=True)
        st.caption('화면은 최대 1,000행을 표시합니다. 다운로드와 분석은 필터 결과 전체를 사용합니다.')
        csv_button(selected,'필터 결과 CSV 내려받기','team_filtered_data.csv')
    with quality:
        st.write('원자료 전체의 항목별 결측 현황입니다. 빈 문자열과 공백도 결측으로 계산합니다.')
        q = quality_table(frame)
        st.dataframe(q,width="stretch",hide_index=True)
        csv_button(q,'품질 보고서 내려받기','team_data_quality.csv')
    report = {'자료':source,'출처와 기간':context,'원본행수':len(frame),'필터후행수':len(selected),
              '검색항목':field,'검색어':query,'범주필터':filter_col,'선택값':values,
              '자료구분':'업로드·검증 전' if choice == 'CSV 업로드' else '시연용 샘플'}
    with analysis:
        st.caption('원자료 탐색에서 적용한 필터를 사용합니다. 숫자 계산에 실패한 값은 제외 건수를 표시합니다.')
        a,b,c = st.columns(3)
        group = a.selectbox('그룹 기준', selected.columns)
        operation = b.selectbox('계산 방식',['건수','평균','중앙값','합계'])
        numeric_candidates = [x for x in selected.columns if x != group]
        metric = c.selectbox('계산할 항목', numeric_candidates, disabled=operation=='건수') if numeric_candidates else None
        if selected.empty:
            st.info('필터 결과가 없습니다. 원자료 탐색에서 조건을 조정하세요.')
        elif operation != '건수' and metric is None:
            st.info('계산하려면 그룹 항목 외에 숫자 항목이 필요합니다.')
        else:
            result, excluded = summarize(selected, group, metric, operation)
            report.update({'그룹':group,'계산방식':operation,'측정항목':metric if operation!='건수' else None,'숫자변환제외행수':excluded})
            st.caption(f'숫자 계산에서 제외한 행: {excluded:,}행. 코드·식별번호를 수치 지표로 사용하지 마세요.')
            if operation in ['평균','중앙값']:
                st.info('각 행을 동일 가중치로 계산합니다. 수료율 등의 비율을 종합할 때는 수강 인원 등 분모를 반영한 별도 집계가 필요합니다.')
            if result.empty: st.info('계산 가능한 숫자가 없습니다. 측정 항목을 바꾸세요.')
            else:
                y = result.columns[-1]
                st.plotly_chart(px.bar(result.sort_values(y,ascending=False).head(30),x=group,y=y,color_discrete_sequence=['#087F8C'],title=f'{group}별 {y}'),width="stretch")
                st.caption('그래프는 값이 큰 30개 그룹까지, 아래 표와 다운로드는 전체 그룹을 제공합니다.')
                st.dataframe(result,width="stretch",hide_index=True)
                csv_button(result,'분석 결과 내려받기','team_analysis.csv')
    with notes:
        st.write('분석 조건과 해석을 한 파일로 묶어 팀원에게 공유하세요.')
        author = st.text_input('작성자',key='report_author')
        memo = st.text_area('발견한 점·해석·추가 확인할 사항',height=140,key='report_memo',placeholder='예: 지역별 자료 수집 범위가 달라 직접적인 공급 격차로 해석할 수 없음')
        report.update({'작성자':author,'검토메모':memo,'생성시각UTC':datetime.now(timezone.utc).isoformat()})
        st.json(report)
        st.download_button('분석 조건·검토 메모 내려받기',json.dumps(report,ensure_ascii=False,indent=2).encode('utf-8'),'team_analysis_record.json','application/json')
        st.caption('메모는 현재 세션에서만 유지됩니다. 파일로 저장한 후 팀 공유 폴더나 GitHub Issue에 첨부하세요.')
        st.markdown('[팀 GitHub Issue 열기](https://github.com/kimsaemi/edu-skill-gap/issues)')
