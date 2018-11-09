import os
import xml.etree.ElementTree as ET
import pickle
from Config import MyConfig
import pprint
from bs4 import BeautifulSoup
import json

pp = pprint.PrettyPrinter(indent=4)


class PreprocessManager():
    def __init__(self):
        self.dir_list = MyConfig.raw_dir_list
        self.dir_path = MyConfig.raw_data_path
        self.vocab, self.all_labels_event, self.all_labels_role = [set() for i in range(3)]

    def preprocess(self):
        '''
        Overall Iterator for whole dataset
        '''
        fnames = self.fname_search()  # list of tuple (sgm file, apf.xml file)
        total_res = []
        for fname in fnames:
            total_res.append(self.process_one_file(fname))
        dataset = []
        for doc in total_res:
            dataset.append(self.process_sentencewise(doc))

        # TODO: save as json file

    def process_sentencewise(self, doc):
        data = []
        entities, val_timexs, events = doc

        # print('## ENTITY ##')
        # pp.pprint(entities[0])
        # print('## VALTIEMX ##')
        # pp.pprint(val_timexs[0])
        # print('\n\n\n## EVENT ##')
        # pp.pprint(events[0])

        for event in events:
            for e_mention in event['event_mention']:
                tmp = {'TYPE': event['TYPE'], 'SUBTYPE': event['SUBTYPE']}
                tmp['raw_sent'] = e_mention['ldc_scope']['text']
                sent_pos = [int(i) for i in e_mention['ldc_scope']['position']]
                entities_in_sent = self.search_entity_in_sentence(entities, sent_pos)
                val_timexs_in_sent = self.search_valtimex_in_sentence(val_timexs, sent_pos)
                final_data = self.packing_sentence(e_mention, tmp, sent_pos, entities_in_sent, val_timexs_in_sent)
                print('raw_sent :   {}'.format(tmp['raw_sent']))
                print(e_mention['anchor'])
                print(sent_pos)
                for e in entities_in_sent:
                    print(e)
                print(val_timexs_in_sent)
                input()

    def packing_sentence(self, e_mention, tmp, sent_pos, entities, valtimexes):
        # TODO : argument가 extent니깐, entity ID 가지고 entity head 가져온 다음에 그 head만 argument로 마크하기 
        
        packed_data = {
            'sentence': [],
            'label_position':[],  # label position ('T' for trigger, 'A' for argument, '*' for None of them
            'EVENT_TYPE' : tmp['TYPE'],
            'EVENT_SUBTYPE' : tmp['SUBTYPE'],
            'entity_position' : []
        }


    @staticmethod
    def search_entity_in_sentence(entities, sent_pos):
        headVSextent = 'head' #'extent'
        entities_in_sent = list()
        check = dict()
        for entity in entities:
            for mention in entity['mention']:
                if sent_pos[0] <= int(mention[headVSextent]['position'][0]) and int(mention[headVSextent]['position'][1]) <= sent_pos[1]:
                    if mention[headVSextent]['position'][0] in check:  # duplicate entity in one word.
                        print('으악!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                        raise ValueError
                    check[mention[headVSextent]['position'][0]] = 1
                    entities_in_sent.append(mention)
        return entities_in_sent

    @staticmethod
    def search_valtimex_in_sentence(valtimex, sent_pos):
        valtimex_in_sent = list()
        for item in valtimex:
            for mention in item['mention']:
                if sent_pos[0] <= int(mention['position'][0]) and sent_pos[1] >= int(mention['position'][1]):
                    valtimex_in_sent.append(mention)
        return valtimex_in_sent

    def fname_search(self):
        '''
        Search dataset directory & Return list of (sgm fname, apf.xml fname)
        '''
        fname_list = list()
        for dir in self.dir_list:
            # To exclude hidden files
            if len(dir) and dir[0] == '.': continue
            full_path = self.dir_path.format(dir)
            flist = os.listdir(full_path)
            for fname in flist:
                if '.sgm' not in fname: continue
                raw = fname.split('.sgm')[0]
                fname_list.append((self.dir_path.format(dir) + raw + '.sgm', self.dir_path.format(dir) + raw + '.apf.xml'))
        return fname_list

    def process_one_file(self, fname):
        # args fname = (sgm fname(full path), xml fname(full path))
        # return some multiple [ sentence, entities, event mention(trigger + argument's information]
        xml_ent_res, xml_valtimex_res, xml_event_res = self.parse_one_xml(fname[1])
        # sgm_ent_res, sgm_event_res = self.parse_one_sgm(fname[0])
        # TODO : merge xml and sgm file together if need.
        return xml_ent_res, xml_valtimex_res, xml_event_res

    def parse_one_xml(self, fname):
        tree = ET.parse(fname)
        root = tree.getroot()
        entities, val_timex, events = [], [], []

        for child in root[0]:
            if child.tag == 'entity':
                entities.append(self.xml_entity_parse(child, fname))
            if child.tag in ['value', 'timex2']:
                val_timex.append(self.xml_value_timex_parse(child, fname))
            if child.tag == 'event':
                events.append(self.xml_event_parse(child, fname))
        return entities, val_timex, events

    def xml_value_timex_parse(self, item, fname):
        child = item.attrib
        child['fname'] = fname
        child['mention'] = []
        for sub in item:
            mention = sub.attrib
            mention['position'] = [sub[0][0].attrib['START'], sub[0][0].attrib['END']]
            mention['text'] = sub[0][0].text
            child['mention'].append(mention)
        return child

    def xml_entity_parse(self, item, fname):
        entity = item.attrib
        entity['fname'] = fname
        entity['mention'] = []
        entity['attribute'] = []  # What is this exactly?
        for sub in item:
            if sub.tag != 'entity_mention': continue
            mention = sub.attrib
            for el in sub:  # charseq and head
                mention[el.tag] = dict()
                mention[el.tag]['position'] = [el[0].attrib['START'], el[0].attrib['END']]
                mention[el.tag]['text'] = el[0].text
            entity['mention'].append(mention)
        return entity

    def xml_event_parse(self, item, fname):
        #  event: one event item
        event = item.attrib
        event['fname'] = fname
        event['argument'] = []
        event['event_mention'] = []
        for sub in item:
            if sub.tag == 'event_argument':
                tmp = sub.attrib
                event['argument'].append(tmp)
                continue
            if sub.tag == 'event_mention':
                mention = sub.attrib  # init dict with mention ID
                mention['argument'] = []
                for el in sub:
                    if el.tag == 'event_mention_argument':
                        one_arg = el.attrib
                        one_arg['position'] = [el[0][0].attrib['START'], el[0][0].attrib['END']]
                        one_arg['text'] = el[0][0].text
                        mention['argument'].append(one_arg)
                    else:  # [extent, ldc_scope, anchor] case
                        for seq in el:
                            mention[el.tag] = dict()
                            mention[el.tag]['position'] = [seq.attrib['START'], seq.attrib['END']]
                            mention[el.tag]['text'] = seq.text
                event['event_mention'].append(mention)
        return event

    def parse_one_sgm(self, fname):
        print('fname :', fname)
        with open(fname, 'r') as f:
            data = f.read()
            soup = BeautifulSoup(data, features='html.parser')

            doc = soup.find('doc')
            doc_id = doc.docid.text
            doc_type = doc.doctype.text.strip()
            date_time = doc.datetime.text
            headline = doc.headline.text if doc.headline else ''

            body = []

            if doc_type == 'WEB TEXT':
                posts = soup.findAll('post')
                for post in posts:
                    poster = post.poster.text
                    post.poster.extract()
                    post_date = post.postdate.text
                    post.postdate.extract()
                    subject = post.subject.text if post.subject else ''
                    if post.subject: post.subject.extract()
                    text = post.text
                    body.append({
                        'poster': poster,
                        'post_date': post_date,
                        'subject': subject,
                        'text': text,
                    })
            elif doc_type in ['STORY', 'CONVERSATION', 'NEWS STORY']:
                turns = soup.findAll('turn')
                for turn in turns:
                    speaker = turn.speaker.text if turn.speaker else ''
                    if turn.speaker: turn.speaker.extract()
                    text = turn.text
                    body.append({
                        'speaker': speaker,
                        'text': text,
                    })

            result = {
                'doc_id': doc_id,
                'doc_type': doc_type,
                'date_time': date_time,
                'headline': headline,
                'body': body,
            }

            return result

    def Data2Json(self, data):
        pass

    def next_train_data(self):
        pass

    def eval_data(self):
        pass


if __name__ == '__main__':
    man = PreprocessManager()
    man.preprocess()
