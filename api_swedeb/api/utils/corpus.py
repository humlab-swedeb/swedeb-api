


class Corpus:
    def __init__(self):
        self.corpus = self.read_corpus()

    def read_corpus(self):
        return 'corpus'
    
    def get_corpus(self):
        return self.corpus
    

def load_corpus():
    c = Corpus()
    c.read_corpus()
    return c