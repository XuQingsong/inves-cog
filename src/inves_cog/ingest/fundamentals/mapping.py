"""Recorded draft generation and explicit human review; no UI is built here."""
import hashlib


class MappingQueue:
    def __init__(self,*,llm,clock,sectors,rows=(),persist=None):
        self.llm,self.clock,self.sectors,self.persist=llm,clock,sectors,persist
        self.rows={row['id']:row for row in rows}
    def draft(self,ticker,segment_raw,*,graph_nodes):
        identifier=hashlib.sha256((ticker+'\0'+segment_raw).encode()).hexdigest()
        if identifier in self.rows: return self.rows[identifier]
        result=self.llm.call('segment_mapping_draft',{'ticker':ticker,'segment_raw':segment_raw,'graph_nodes':graph_nodes})
        ids=result.get('graph_node_ids'); reason=result.get('reason')
        if not isinstance(ids,list) or not all(isinstance(value,str) for value in ids) or not isinstance(reason,str) or not reason:
            raise ValueError('Invalid mapping draft response')
        known={row['id'] for row in graph_nodes}
        if set(ids)-known: raise ValueError('Draft contains unknown graph node IDs')
        row={'id':identifier,'ticker':ticker,'segment_raw':segment_raw,'graph_node_ids':ids,
             'drafted_by':'glm-5.3','draft_reason':reason,'status':'待审核','reviewed_at':None,
             'reviewer':None,'segment_std':None,'health_codes':['segment_unmapped']}
        self.rows[identifier]=row
        if self.persist: self.persist(row)
        return row
    def list_pending_mappings(self,sector=None):
        return [row for row in self.rows.values() if row['status']=='待审核' and (sector is None or self.sectors.get(row['ticker'])==sector)]
    def confirm_mappings(self,ids,reviewer,decision):
        if not reviewer or not reviewer.strip() or decision not in {'已确认','驳回'}: raise ValueError('Reviewer and valid decision required')
        if len(set(ids))!=len(ids) or any(identifier not in self.rows for identifier in ids): raise ValueError('Unknown or duplicate mapping IDs')
        for identifier in ids:
            row=self.rows[identifier]
            row.update(status=decision,reviewed_at=self.clock.now_utc(),reviewer=reviewer,
                       segment_std=list(row['graph_node_ids']) if decision=='已确认' else None,
                       health_codes=[] if decision=='已确认' else ['segment_unmapped'])
            if self.persist: self.persist(row)
        return [self.rows[identifier] for identifier in ids]


_queue=None
def configure(queue):
    global _queue
    _queue=queue
def list_pending_mappings(sector):
    if _queue is None: raise RuntimeError('Mapping queue not configured')
    return _queue.list_pending_mappings(sector)
def confirm_mappings(ids,reviewer,decision):
    if _queue is None: raise RuntimeError('Mapping queue not configured')
    return _queue.confirm_mappings(ids,reviewer,decision)
