"""Hash-bound BODY localization; no claim validation or scientific authority.

Exact matching is preferred. An explicit source-bound context can additionally
permit only length-preserving NBSP/SPACE substitution and quote-terminal SPACE.
The model payload is never edited; the source span and model quote stay distinct.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from scripts.search_plan_v24_alpha320a_v4_localizer import (
    localize_exact_body_quote, SUCCESS, NONUNIQUE, NOT_FOUND,
)

VERSION='source_quote_localization_whitespace_v1'
CONTEXT_VERSION='source_bound_BODY_localization_context_v1'


class SourceQuoteLocalizationError(ValueError):
    def __init__(self,reason,detail=None):
        self.reason=reason;self.detail=detail
        super().__init__(reason+(':'+detail if detail else ''))


def _sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _digest(value):
    return _sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')))


def _require(ok,detail):
    if not ok:raise SourceQuoteLocalizationError('SOURCE_ANCHOR_INTEGRITY_FAILURE',detail)


def context_from_window(document,window,*,source_artifact,expected_source_sha256,authorized_anchor_ids):
    """Caller supplies the already frozen source hash and authorized BODY scope.

    A hash is an integrity binding, not independent scientific approval. This
    contract supports the existing ArticleJSON-backed source-window interface.
    """
    fragments=window.get('fragments') or [window]
    _require(len(fragments)==len(document['paragraphs']),'fragment_paragraph_count')
    rows=[]
    for f,p in zip(fragments,document['paragraphs']):
        _require(p['text']==f['text'],'fragment_paragraph_text')
        rows.append({'anchor_id':p['span_id'],'body_start':p['start_offset'],'body_end':p['end_offset'],
            'section_index':f['section_index'],'source_char_start':f['source_char_start'],
            'source_char_end':f['source_char_end'],'source_text_sha256':_sha(f['text'])})
    value={'schema_version':CONTEXT_VERSION,'matching_policy_version':VERSION,
           'source_artifact':str(Path(source_artifact).resolve()),'source_sha256':expected_source_sha256,
           'document_sha256':_digest(document),'body_sha256':_sha(document['body_text']),
           'authorized_anchor_ids':list(authorized_anchor_ids),'paragraph_source_map':rows}
    article=_verify_context(document,value)
    value['source_identity']={k:str(article[k]) for k in ('pmcid','pmid')}
    return value


def _verify_context(document,context):
    try:
        _require(context['schema_version']==CONTEXT_VERSION and context['matching_policy_version']==VERSION,'context_version')
        raw=Path(context['source_artifact']).read_bytes()
        _require(hashlib.sha256(raw).hexdigest()==context['source_sha256'],'frozen_source_hash_mismatch')
        article=json.loads(raw)
        if context.get('source_identity'):
            _require(context['source_identity']=={k:str(article[k]) for k in ('pmcid','pmid')},'source_identity_mismatch')
        _require(_digest(document)==context['document_sha256'] and _sha(document['body_text'])==context['body_sha256'],'construction_document_hash_mismatch')
        ps=document['paragraphs'];maps=context['paragraph_source_map']
        _require(len(ps)==len(maps)>0 and document['body_text']=='\n\n'.join(p['text'] for p in ps),'BODY_paragraph_accounting')
        ids=[p['span_id'] for p in ps];authorized=context['authorized_anchor_ids']
        _require(len(ids)==len(set(ids)) and bool(authorized) and len(authorized)==len(set(authorized)) and set(authorized)<=set(ids),'authorized_BODY_anchor_identity')
        cursor=0
        for p,m in zip(ps,maps):
            _require(p['span_id']==m['anchor_id'] and p['start_offset']==m['body_start']==cursor and p['end_offset']==m['body_end']==cursor+len(p['text']),'BODY_anchor_coordinates')
            _require(type(m['section_index']) is int and 0<=m['section_index']<len(article['sections']),'source_section_identity')
            source=article['sections'][m['section_index']]['text'];a,b=m['source_char_start'],m['source_char_end']
            _require(type(a) is int and type(b) is int and 0<=a<b<=len(source),'source_coordinates')
            _require(source[a:b]==p['text']==document['body_text'][m['body_start']:m['body_end']] and _sha(source[a:b])==m['source_text_sha256'],'original_source_text_or_hash')
            cursor=p['end_offset']+2
        return article
    except SourceQuoteLocalizationError:raise
    except (KeyError,TypeError,ValueError,OSError,IndexError) as exc:
        raise SourceQuoteLocalizationError('SOURCE_ANCHOR_INTEGRITY_FAILURE',type(exc).__name__) from exc


def _occurrences(needle,haystack):
    start=0
    while True:
        pos=haystack.find(needle,start)
        if pos<0:return
        yield pos,pos+len(needle)
        start=pos+1


def _legitimate(intervals,document,authorized):
    accepted=[];outside=False
    for a,b in intervals:
        parents=[p for p in document['paragraphs'] if p['start_offset']<=a<b<=p['end_offset']]
        if len(parents)==1 and parents[0]['span_id'] in authorized:accepted.append((a,b,parents[0]))
        else:outside=True
    return accepted,outside


def localize_source_quote(raw_model_quote,document,context):
    """Original offsets are recoverable because folding never changes length.

    Only U+0020 can be ignored at the model quote's trailing boundary. Tabs,
    newlines, repeated internal whitespace and all scientific text are unchanged.
    Source suffix spaces need not be included in a matching substring; they are
    never deleted from the source or retroactively treated as model evidence.
    """
    _require(bool(context.get('source_identity')),'source_identity_required')
    _verify_context(document,context)
    if not isinstance(raw_model_quote,str) or not raw_model_quote:
        raise SourceQuoteLocalizationError('SOURCE_QUOTE_NOT_FOUND','empty_quote')
    body=document['body_text'];authorized=set(context['authorized_anchor_ids'])
    exact,outside=_legitimate(_occurrences(raw_model_quote,body),document,authorized)
    if len(exact)>1:raise SourceQuoteLocalizationError('SOURCE_QUOTE_AMBIGUOUS','multiple_exact_authorized_spans')
    changes=[];method='EXACT_SOURCE_MATCH'
    if exact:
        a,b,p=exact[0]
    else:
        core=raw_model_quote.rstrip(' ')
        if not core:raise SourceQuoteLocalizationError('SOURCE_QUOTE_NOT_FOUND','empty_after_boundary_SPACE')
        # A one-codepoint substitution; not NFKC, strip(), whitespace collapse,
        # punctuation handling, unit conversion, edit distance or fuzzy search.
        folded=body.replace('\u00a0',' ');needle=core.replace('\u00a0',' ')
        matches,fold_outside=_legitimate(_occurrences(needle,folded),document,authorized)
        if len(matches)>1:raise SourceQuoteLocalizationError('SOURCE_QUOTE_AMBIGUOUS','multiple_permitted_equivalent_spans')
        if not matches:
            if outside or fold_outside:raise SourceQuoteLocalizationError('SOURCE_QUOTE_OUTSIDE_AUTHORIZED_BODY')
            raise SourceQuoteLocalizationError('SOURCE_QUOTE_NOT_FOUND','no_span_under_permitted_whitespace_policy')
        a,b,p=matches[0]
        original=body[a:b]
        for i,(source,model) in enumerate(zip(original,core)):
            if source!=model:
                if {source,model}!={'\u00a0',' '}:
                    raise SourceQuoteLocalizationError('SOURCE_QUOTE_DISALLOWED_DIFFERENCE')
                changes.append({'operation':'NBSP_SPACE_EQUIVALENCE','quote_relative_index':i,'body_character_index':a+i,
                    'source_code_point':f'U+{ord(source):04X}','model_code_point':f'U+{ord(model):04X}'})
        if len(core)!=len(raw_model_quote):
            changes.append({'operation':'IGNORE_MODEL_TRAILING_U0020_AT_QUOTE_BOUNDARY','quote_char_start':len(core),'quote_char_end':len(raw_model_quote),'count':len(raw_model_quote)-len(core)})
        _require(bool(changes),'fallback_without_permitted_difference')
        method='PERMITTED_WHITESPACE_EQUIVALENT'
    original=body[a:b]
    m=next(x for x in context['paragraph_source_map'] if x['anchor_id']==p['span_id'])
    source_start=m['source_char_start']+a-p['start_offset'];source_end=source_start+len(original)
    return {'matching_policy_version':VERSION,'localization_status':method,'accepted':True,
        'exact_match_boolean':raw_model_quote.encode()==original.encode(),
        'raw_model_quote':raw_model_quote,'raw_model_quote_sha256':_sha(raw_model_quote),
        'original_source_text':original,'original_source_text_sha256':_sha(original),
        'permitted_whitespace_differences':changes,'original_anchor_id':p['span_id'],
        'original_source_coordinates':{'source_artifact':context['source_artifact'],'source_sha256':context['source_sha256'],
            'section_index':m['section_index'],'char_start':source_start,'char_end':source_end,
            'coordinate_space':'ArticleJSON_section_Unicode_codepoints','end_semantics':'exclusive'},
        'source_field':'body','body_document_start_offset':a,'body_document_end_offset':b,
        'paragraph_local_start_offset':a-p['start_offset'],'paragraph_local_end_offset':b-p['start_offset'],
        'paragraph_ordinal':p['ordinal'],'anchor_id':p['span_id'],
        'scientific_quality_assessed':False,'scientific_authorization':False}


def localize_for_quality(raw_quote,document,*,context=None):
    """Legacy exact behavior stays exact-only unless a hash-bound context exists.

    No failed localization is allowed to forward null coordinates to Quality.
    """
    if context is not None:return localize_source_quote(raw_quote,document,context)
    result=localize_exact_body_quote(raw_quote,document['body_text'],document['paragraphs'])
    state=result['development_v4_localization_state']
    if state!=SUCCESS:
        code='SOURCE_QUOTE_AMBIGUOUS' if state==NONUNIQUE else 'SOURCE_QUOTE_NOT_FOUND' if state==NOT_FOUND else 'SOURCE_ANCHOR_INTEGRITY_FAILURE'
        raise SourceQuoteLocalizationError(code,state)
    return {**result,'accepted':True,'localization_status':'EXACT_SOURCE_MATCH',
        'matching_policy_version':'legacy_V4_exact_only','exact_match_boolean':True,
        'raw_model_quote':raw_quote,'raw_model_quote_sha256':_sha(raw_quote),
        'original_source_text':raw_quote,'original_source_text_sha256':_sha(raw_quote),
        'permitted_whitespace_differences':[],'original_anchor_id':result['anchor_id']}
