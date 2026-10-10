import json

import pytest

from app.room_service.chatbot.claim_verification import check_claims, ClaimIssues, retained_answer
from app.room_service.chatbot.providers import GenerationResult
from app.room_service.chatbot.schemas import ChatAskRequest
from test_agent_workflow import Client, answer, draft, workflow, service, QUESTION


def records():
    return [dict(claim_id='summary', kind='procedure', text='Tra cứu theo mã khách hàng',
        source_ranks=[2], rendered='Tra cứu theo mã khách hàng [2].')]


def verdicts():
    return [dict(claim_id='summary',source_ids=[2],kind='procedure',supported=True,
        reason='Đúng hướng dẫn của nhà cung cấp.')]


class Verifier:
    def __init__(self, result): self.result = result
    def request_json(self, prompt, schema):
        assert 'không tự là nghĩa vụ pháp luật' in prompt
        return json.dumps(dict(verdicts=self.result)), {}


def test_verifier_returns_complete_claim_ids_sources_and_reasons():
    result=check_claims(Verifier(verdicts()),'Tra cứu thế nào?',records()[0]['rendered'],
        [dict(rank=2,content='Tra cứu theo mã khách hàng.',context_complete=False)],records())
    assert not result and result.verdicts[0]['source_ids']==[2]


@pytest.mark.parametrize('change',[{'claim_id':'invented'},{'source_ids':[3]},{'supported':'true'}])
def test_incomplete_invented_or_misclassified_positive_verdict_is_rejected(change):
    value=verdicts()[0];value.update(change)
    with pytest.raises(ValueError):
        check_claims(Verifier([value]),'Question?',records()[0]['rendered'],
            [dict(rank=2,content='Tra cứu theo mã khách hàng.')],records())


def test_kind_mismatch_rejects_only_that_claim_and_preserves_valid_verdicts():
    one=records()[0];two=dict(one,claim_id='steps:0')
    wrong=dict(verdicts()[0],kind='regulation')
    valid=dict(verdicts()[0],claim_id='steps:0')
    result=check_claims(Verifier([wrong,valid]),'Tra cứu thế nào?',one['rendered'],
        [dict(rank=2,content='Tra cứu theo mã khách hàng.')],[one,two])
    assert len(result)==1 and result.verdicts[0]['code']=='claim_kind_mismatch'
    assert not result.verdicts[0]['supported'] and result.verdicts[1]['supported']


def test_retained_gap_reason_is_not_reinterpreted_as_an_uncited_legal_duty():
    from app.room_service.chatbot.legal_retrieval import evidence_issues
    good=records()[0];bad=dict(good,claim_id='limitations:0')
    failed=dict(verdicts()[0],claim_id='limitations:0',supported=False,
        reason='Mệnh đề phải được phân loại source_limit thay vì procedure.')
    generated=GenerationResult(good['rendered'],'gemini-agent',claim_records=(good,bad))
    retained=retained_answer(generated,ClaimIssues([*verdicts(),failed]))
    issues=evidence_issues(retained.text,[dict(rank=2,content='Tra cứu theo mã khách hàng.')],'Tra cứu?',claim_records=retained.claim_records)
    assert not any('chưa gắn trích dẫn' in issue for issue in issues)
    assert 'source_limit' not in retained.text and 'procedure' not in retained.text


def test_partial_retention_never_keeps_rejected_claim():
    good=records()[0]
    bad=dict(good,claim_id='steps:0',rendered='Phải trả 100% phí [2].')
    generated=GenerationResult(good['rendered']+'\n'+bad['rendered'],'gemini-agent',claim_records=(good,bad))
    failed=dict(verdicts()[0],claim_id='steps:0',supported=False,reason='Nguồn chưa nêu hoàn toàn bộ phí.')
    result=retained_answer(generated,ClaimIssues([*verdicts(),failed]))
    assert good['rendered'] in result.text and bad['rendered'] not in result.text
    assert failed['reason'] not in result.text and 'steps:0' not in result.text
    assert 'Chưa đủ căn cứ' in result.text and len(result.text)<=3500


def test_verifier_diagnostic_is_not_an_additional_legal_claim_in_retained_answer():
    from app.room_service.chatbot.legal_retrieval import evidence_issues
    good=records()[0];bad=dict(good,claim_id='limitations:0')
    failed=dict(verdicts()[0],claim_id='limitations:0',supported=False,
        reason='Nguồn 2 hoàn toàn không có quy định về chia tiền nước khoán.')
    check=ClaimIssues([*verdicts(),failed])
    generated=GenerationResult(good['rendered'],'gemini-agent',claim_records=(good,bad))
    kept=retained_answer(generated,check)
    assert not evidence_issues(kept.text,[dict(rank=2,content='Tra cứu theo mã khách hàng.')],'',claim_records=kept.claim_records)
    assert failed['reason'] not in kept.text and check.verdicts[-1]['reason']==failed['reason']


def test_no_retention_on_missing_verdict_or_total_rejection():
    generated=GenerationResult(records()[0]['rendered'],'gemini-agent',claim_records=tuple(records()))
    assert retained_answer(generated,[]) is None
    failed=dict(verdicts()[0],supported=False)
    assert retained_answer(generated,ClaimIssues([failed])) is None


def test_writer_repair_preserves_accepted_line_exactly():
    agent,selector,client=workflow()
    original=agent.writer.synthesize(QUESTION,draft())
    changed=answer();changed['summary']['text']='Một câu mới không được phép thay ý đã xác nhận'
    client.result=changed
    fixed=agent.repair_legal_answer(QUESTION,original,issues=['steps:0 cần sửa phân loại'],accepted_ids=['summary'])
    assert fixed.claim_records[0]==original.claim_records[0]
    assert client.writes==2


@pytest.mark.parametrize('content_supported', [True, False])
def test_classification_annotation_is_repaired_then_content_is_verified_again(content_supported):
    class RepeatedKindClient(Client):
        supports_claim_records=True
        def check_legal_evidence(self,question,text,contexts,*,claim_records=()):
            self.checks+=1
            indexed={c['claim_id']:c for c in claim_records}
            summary=indexed['summary']
            if self.checks==1:
                assert summary['kind']=='procedure'
                verdict=dict(claim_id='summary',source_ids=[1],kind='regulation',supported=False,
                    declared_kind='procedure',code='claim_kind_mismatch',reason='Nội dung thuộc quy định; sửa phân loại.')
            else:
                assert summary['kind']=='regulation'
                verdict=dict(claim_id='summary',source_ids=[1],kind='regulation',supported=content_supported,
                    reason='Đã đối chiếu lại nội dung và nguồn sau sửa phân loại.')
            return ClaimIssues([verdict,dict(claim_id='steps:0',source_ids=[1],kind='recommendation',
                supported=True,reason='Khuyến nghị đối chiếu được nguồn hỗ trợ.')])
    data=answer();data['summary']['kind']='procedure';data['steps'][0]['kind']='recommendation'
    agent,selector,client=workflow(RepeatedKindClient(result=data))
    result=service(agent).ask(ChatAskRequest(message=QUESTION))
    assert selector.calls==1 and client.writes==client.checks==2
    assert (data['summary']['text'] in result.answer)==content_supported
    assert any(s.get('classification_annotations_updated') for s in result.agent_trace)
    if not content_supported: assert result.partial_answer


@pytest.mark.parametrize('change,accepted', [
    ({'source_ids':[2]},[]), ({'claim_id':'invented'},[]), ({},['summary'])])
def test_kind_repair_cannot_change_an_accepted_claim_or_other_source_binding(change,accepted):
    data=answer();data['summary']['kind']='procedure'
    agent,selector,client=workflow(Client(result=data))
    original=agent.writer.synthesize(QUESTION,draft())
    issue=dict(claim_id='summary',source_ids=[1],kind='regulation',supported=False,
        declared_kind='procedure',code='claim_kind_mismatch',reason='Sửa phân loại.')
    issue.update(change)
    fixed=agent.repair_legal_answer(QUESTION,original,issues=[json.dumps(issue)],accepted_ids=accepted)
    assert fixed.claim_records[0]['kind']=='procedure'


def test_malformed_repair_keeps_original_draft_for_per_claim_retention():
    class RepairFailure(Client):
        def request_json(self, prompt, schema, **kwargs):
            if self.writes:
                self.writes+=1
                raise RuntimeError('Writer unavailable during repair')
            return super().request_json(prompt,schema,**kwargs)
        def check_legal_evidence(self, question, text, contexts, *, claim_records=()):
            self.checks+=1
            return ClaimIssues([
                dict(claim_id='summary',source_ids=[1],kind='regulation',supported=True,reason='Đúng nội dung nguồn.'),
                dict(claim_id='steps:0',source_ids=[1],kind='regulation',supported=False,reason='Ý này chưa được nguồn hỗ trợ.')])
    agent,selector,client=workflow(RepairFailure())
    result=service(agent).ask(ChatAskRequest(message=QUESTION))
    assert result.generation_provider=='gemini-agent' and result.partial_answer
    assert answer()['summary']['text'] in result.answer
    assert answer()['steps'][0]['text'] not in result.answer
    assert selector.calls==1 and client.writes==client.checks==2


def test_service_retains_supported_claim_after_bounded_repair():
    class PartialClient(Client):
        def check_legal_evidence(self,question,text,contexts):
            self.checks+=1
            return ClaimIssues([
                dict(claim_id='summary',source_ids=[1],kind='regulation',supported=True,reason='Đúng nội dung nguồn.'),
                dict(claim_id='steps:0',source_ids=[1],kind='recommendation',supported=False,reason='Phân loại cần sửa rõ khuyến nghị.')])
    agent,selector,client=workflow(PartialClient())
    result=service(agent).ask(ChatAskRequest(message=QUESTION))
    assert result.generation_provider=='gemini-agent'
    assert client.writes==client.checks==2 and selector.calls==1
    assert result.partial_answer and any(s['status']=='partial_retained' for s in result.agent_trace)


def test_rule_rejection_is_localized_and_supported_summary_survives():
    class IncorrectStepClient(Client):
        def check_legal_evidence(self,question,text,contexts):
            self.checks+=1
            return ClaimIssues([
                dict(claim_id='summary',source_ids=[1],kind='regulation',supported=True,reason='Đúng nội dung nguồn.'),
                dict(claim_id='steps:0',source_ids=[1],kind='regulation',supported=True,reason='Verdict sai bị bộ quy tắc chặn.')])
    result_data=answer();result_data['steps'][0]['text']='Chủ trọ phải hoàn trả toàn bộ tiền cọc cho người thuê'
    agent,selector,client=workflow(IncorrectStepClient(result=result_data))
    result=service(agent).ask(ChatAskRequest(message=QUESTION))
    assert result.generation_provider=='gemini-agent' and result.partial_answer
    assert 'hoàn trả toàn bộ' not in result.answer
    assert selector.calls==1 and client.writes==client.checks==2
