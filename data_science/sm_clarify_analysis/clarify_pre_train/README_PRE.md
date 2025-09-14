
```

| Analiz Tipi           | Metod Adı                  | Ne Zaman Kullanılır?                                |
| --------------------- | -------------------------- | --------------------------------------------------- |
| Pre-training Bias     | `run_pre_training_bias()`  | Model eğitilmeden önce veri taraflı önyargı analizi |
| Post-training Bias    | `run_post_training_bias()` | Model eğitildikten sonra veri + model analizi       |
| Explainability (SHAP) | `run_explainability()`     | Model kararlarını açıklamak için                    |


```


🛫 Carrier (Havayolu) için Pre-Training Bias Analizi Ne Demek?

1. Facet Nedir?
Burada facet = "carrier" yani havayolu firması.

Yani her uçuş kaydının ait olduğu havayolu firması temelinde verinin özellikleri ve etiketi (dep_delay) analiz ediliyor.

2. Neyi Ölçüyoruz?
Örneğin, bu metriklerle bakıyoruz:

Metrik	Ne Anlatır?

```
Class Imbalance (CI)	dep_delay (gecikme) etiketinde havayolu firmalarına göre dengesizlik var mı? Mesela bazı havayollarında çoğunlukla gecikme yokken, bazılarında çok gecikme olabilir.

Difference in Positive Label (DPL)	Gecikme olmayan (label=0) uçuşların havayolu firmalarına göre oran farkı. Belli firmalar avantajlı mı?

Kullback-Leibler Divergence (KL)	Farklı havayolu firmalarının uçuş süresi, mesafe gibi dağılımlarının birbirinden ne kadar farklı olduğunu gösterir.

Jensen-Shannon Divergence (JS)	KL'nın simetrik ve daha dengeli versiyonu. Havayolu firmaları arasındaki veri farklarını ölçer.

Lp-norm (LP)	Farklı veri dağılımları arasındaki uzaklığı sayısal olarak gösterir.

Total Variation Distance (TVD)	İki dağılım arasındaki maksimum farkı verir.

Kolmogorov-Smirnov (KS)	İki veri setinin kümülatif dağılım fonksiyonları arasındaki farkı istatistiksel olarak ölçer.

Conditional Demographic Disparity (CDD)	Gecikme oranının carrier gibi özelliklere göre demografik farklılıklarını ölçer.
```

3. Neden Önemli?
Eğer belirli bir havayolu için gecikme oranı diğerlerine göre çok farklıysa (mesela çok daha yüksek veya düşükse),

Bu bias yani veride dengesizlik demektir.

Model böyle bir veriyle eğitilirse, örneğin bazı havayollarına karşı daha önyargılı (adil olmayan) tahminler yapabilir.

4. Gerçek Dünya Örneği
Diyelim ki “UA” adlı havayolu genelde uçuşları zamanında yapıyor (label=0 oranı yüksek),

Ama “DL” havayolunda gecikmeler çok daha fazla,

Bu farklar DPL, CI, KL gibi metriklerle ölçülür.

Eğer farklar çok yüksekse, modelin "DL" uçuşlarını daha sık gecikmeli tahmin etmesi normal olur ama bu durum bazı durumlarda istenmeyebilir.

📊 Özet:
Carrier facet analizi, her havayolunun uçuş verisinin kalitesini, gecikme oranlarını, ve diğer uçuş özelliklerinin dağılımını inceler.

Amaç, verideki önyargı ve dengesizlikleri önceden tespit edip, modelin adil ve güvenilir tahminler yapmasını sağlamak.