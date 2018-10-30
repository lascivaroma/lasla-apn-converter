LASLA APN Converter
===================

The `cli.py` in this folder is a small script able to convert the proprietary
APN format of the LASLA to traditional TSV. You can also convert the tag system
of the LASLA into more traditional tags. See below for examples.

We recommend to do a `chmod +x cli.py`.

## Examples

### Input

```
PLA&0001MVNDVS               1mundum                   2,1,1       A231       A
PLA&0001ET                   2et                       2,1,1       S          S
PLA&0001HIC                  1hoc                      2,1,1       I 31       I6
PLA&0001QVICVMQVE            1quodcumque               2,1,1       J 31       J6
```

### Simple Command

Shell : `./cli.py datasets/file.APN output`

output/file.tsv will be like

```tsv
form	lemma	morph	pos	index
mundum	MVNDVS1	A231       	A	0001
et	ET2	S          	S	0001
hoc	HIC1	I 31       	I6	0001
quodcumque	QVICVMQVE1	J 31       	J6	0001
```

### Morph-Converting Command

Shell : `./cli.py datasets/file.APN output --enhanced_morph`

output/file.tsv will be like

```tsv
form	lemma	morph	pos	index
mundum	MVNDVS1	Case=Acc|Numb=Sing	NOM2	0001
et	ET2	MORPH=EMPTY	CONcoo	0001
hoc	HIC1	Case=Acc|Numb=Sing	PROdem	0001
quodcumque	QVICVMQVE1	Case=Acc|Numb=Sing	PROrel	0001
```